import json
import boto3
import requests
from datetime import datetime, timedelta
import os

def lambda_handler(event, context):
    """
    Enhanced Swing Trading Bot with Multi-Source Sentiment Analysis
    Simplified version without pandas for Lambda compatibility
    """
    
    # Get environment variables
    bucket_name = os.environ['BUCKET_NAME']
    email_recipient = 'mhussain.myindia@gmail.com'
    secret_name = os.environ.get('SECRET_NAME', 'swing-alpaca/papter-trading/keys')
    
    # Initialize AWS clients
    s3 = boto3.client('s3')
    ses = boto3.client('ses')
    secrets_client = boto3.client('secretsmanager')
    
    try:
        # Get API keys from Secrets Manager
        secret_response = secrets_client.get_secret_value(SecretId=secret_name)
        api_keys = json.loads(secret_response['SecretString'])
        
        # Get symbols from event
        symbols = event.get('symbols', ['AAPL', 'NVDA', 'MSFT', 'AMD', 'TSLA', 'ARKK', 'BOTZ', 'QQQ'])
        
        results = []
        
        for symbol in symbols:
            print(f"Processing {symbol}...")
            
            # Get stock data from Alpaca
            stock_data = get_stock_data(symbol, api_keys)
            if not stock_data:
                continue
                
            # Calculate technical indicators
            rsi = calculate_rsi(stock_data)
            ema = calculate_ema(stock_data)
            current_price = stock_data[-1]['close']
            
            # Get sentiment analysis
            sentiment_data = get_multi_source_sentiment(symbol, api_keys)
            
            # Generate enhanced signal with sentiment
            signal = generate_enhanced_signal(current_price, rsi, ema, sentiment_data)
            
            result = {
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'price': current_price,
                'rsi': rsi,
                'ema': ema,
                'sentiment': sentiment_data,
                'signal': signal
            }
            
            results.append(result)
            
            # Store individual symbol data
            store_symbol_data(s3, bucket_name, symbol, result)
        
        # Store daily analysis
        daily_analysis = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'timestamp': datetime.now().isoformat(),
            'symbols_analyzed': len(results),
            'signals_generated': len([r for r in results if r['signal']['action'] != 'HOLD']),
            'results': results
        }
        
        store_daily_analysis(s3, bucket_name, daily_analysis)
        
        # Send comprehensive email notification (always send)
        send_comprehensive_email_notification(ses, email_recipient, daily_analysis, 'sentiment-enhanced')
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Enhanced swing trading analysis completed successfully',
                'symbols_processed': len(results),
                'signals_generated': len([r for r in results if r['signal']['action'] != 'HOLD'])
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def get_stock_data(symbol, api_keys):
    """Get stock data from Alpaca API"""
    try:
        headers = {
            'APCA-API-KEY-ID': api_keys['ALPACA_API_KEY'],
            'APCA-API-SECRET-KEY': api_keys['ALPACA_SECRET_KEY']
        }
        
        # Use correct Alpaca data API endpoint
        url = f"https://data.alpaca.markets/v2/stocks/{symbol}/bars"
        start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
        
        params = {
            'timeframe': '1Day',
            'limit': 30,
            'start': start_date
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        bars = data.get('bars', [])
        
        if not bars:
            print(f"No bars returned for {symbol}")
            return None
            
        return [{'close': bar['c'], 'high': bar['h'], 'low': bar['l']} for bar in bars]
        
    except Exception as e:
        print(f"Error fetching stock data for {symbol}: {e}")
        return None

def calculate_rsi(stock_data, period=14):
    """Calculate RSI indicator"""
    if len(stock_data) < period + 1:
        return 50
    
    closes = [bar['close'] for bar in stock_data]
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return round(rsi, 2)

def calculate_ema(stock_data, period=20):
    """Calculate EMA indicator"""
    if len(stock_data) < period:
        return sum(bar['close'] for bar in stock_data) / len(stock_data)
    
    closes = [bar['close'] for bar in stock_data]
    multiplier = 2 / (period + 1)
    
    ema = sum(closes[:period]) / period
    
    for price in closes[period:]:
        ema = (price * multiplier) + (ema * (1 - multiplier))
    
    return round(ema, 2)

def get_multi_source_sentiment(symbol, api_keys):
    """Get sentiment from multiple sources"""
    sentiment_data = {
        'overall_score': 0,
        'confidence': 0,
        'sources': {}
    }
    
    scores = []
    weights = []
    
    # Finnhub sentiment
    try:
        finnhub_sentiment = get_finnhub_sentiment(symbol, api_keys.get('FINNHUB_API_KEY'))
        if finnhub_sentiment is not None:
            sentiment_data['sources']['finnhub'] = finnhub_sentiment
            scores.append(finnhub_sentiment)
            weights.append(0.4)
    except Exception as e:
        print(f"Finnhub sentiment error: {e}")
    
    # NewsAPI sentiment
    try:
        news_sentiment = get_news_sentiment(symbol, api_keys.get('NEWSAPI_KEY'))
        if news_sentiment is not None:
            sentiment_data['sources']['news'] = news_sentiment
            scores.append(news_sentiment)
            weights.append(0.3)
    except Exception as e:
        print(f"News sentiment error: {e}")
    
    # Reddit sentiment
    try:
        reddit_sentiment = get_reddit_sentiment(symbol, api_keys)
        if reddit_sentiment is not None:
            sentiment_data['sources']['reddit'] = reddit_sentiment
            scores.append(reddit_sentiment)
            weights.append(0.3)
    except Exception as e:
        print(f"Reddit sentiment error: {e}")
    
    # Calculate weighted average
    if scores:
        total_weight = sum(weights)
        weighted_score = sum(s * w for s, w in zip(scores, weights)) / total_weight
        sentiment_data['overall_score'] = round(weighted_score, 2)
        sentiment_data['confidence'] = min(len(scores) * 0.33, 1.0)
    
    return sentiment_data

def get_finnhub_sentiment(symbol, api_key):
    """Get sentiment from Finnhub"""
    if not api_key:
        return None
        
    try:
        url = f"https://finnhub.io/api/v1/news-sentiment"
        params = {'symbol': symbol, 'token': api_key}
        
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        return data.get('sentiment', 0)
        
    except Exception as e:
        print(f"Finnhub API error: {e}")
        return None

def get_news_sentiment(symbol, api_key):
    """Get sentiment from NewsAPI with simple analysis"""
    if not api_key:
        return None
        
    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            'q': symbol,
            'apiKey': api_key,
            'pageSize': 10,
            'sortBy': 'publishedAt'
        }
        
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        articles = data.get('articles', [])
        
        if not articles:
            return 0
        
        # Simple sentiment analysis based on keywords
        positive_words = ['up', 'rise', 'gain', 'bull', 'positive', 'growth', 'strong']
        negative_words = ['down', 'fall', 'drop', 'bear', 'negative', 'decline', 'weak']
        
        sentiment_score = 0
        for article in articles:
            title = (article.get('title', '') + ' ' + article.get('description', '')).lower()
            
            pos_count = sum(1 for word in positive_words if word in title)
            neg_count = sum(1 for word in negative_words if word in title)
            
            if pos_count > neg_count:
                sentiment_score += 1
            elif neg_count > pos_count:
                sentiment_score -= 1
        
        return round(sentiment_score / len(articles), 2)
        
    except Exception as e:
        print(f"NewsAPI error: {e}")
        return None

def get_reddit_sentiment(symbol, api_keys):
    """Get sentiment from Reddit"""
    try:
        # Simple placeholder - Reddit API requires OAuth which is complex for Lambda
        # In a real implementation, you'd use PRAW library with proper authentication
        return 0
        
    except Exception as e:
        print(f"Reddit sentiment error: {e}")
        return None

def generate_enhanced_signal(price, rsi, ema, sentiment_data):
    """Generate trading signal with sentiment enhancement"""
    base_signal = "HOLD"
    strength = "WEAK"
    confidence = sentiment_data.get('confidence', 0)
    sentiment_score = sentiment_data.get('overall_score', 0)
    
    # Adjust thresholds based on sentiment confidence
    rsi_buy_threshold = 30 + (sentiment_score * 5 * confidence)
    rsi_sell_threshold = 70 - (sentiment_score * 5 * confidence)
    
    # Generate signal
    if rsi < rsi_buy_threshold and price > ema:
        base_signal = "BUY"
        if confidence > 0.7 and sentiment_score > 0.5:
            strength = "STRONG"
        elif confidence > 0.4:
            strength = "MODERATE"
    elif rsi > rsi_sell_threshold and price < ema:
        base_signal = "SELL"
        if confidence > 0.7 and sentiment_score < -0.5:
            strength = "STRONG"
        elif confidence > 0.4:
            strength = "MODERATE"
    
    return {
        'action': base_signal,
        'strength': strength,
        'confidence': round(confidence, 2),
        'sentiment_influence': round(sentiment_score, 2),
        'reasoning': f"RSI: {rsi}, EMA: {ema}, Price: {price}, Sentiment: {sentiment_score}"
    }

def store_symbol_data(s3, bucket_name, symbol, data):
    """Store individual symbol data in S3"""
    try:
        date_str = datetime.now().strftime('%Y-%m-%d')
        key = f"symbols/{symbol}/{date_str}.json"
        
        s3.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=json.dumps(data, indent=2),
            ContentType='application/json'
        )
        
    except Exception as e:
        print(f"Error storing symbol data: {e}")

def store_daily_analysis(s3, bucket_name, analysis):
    """Store daily analysis in S3"""
    try:
        date_str = datetime.now().strftime('%Y-%m-%d')
        key = f"daily-analysis/{date_str}.json"
        
        s3.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=json.dumps(analysis, indent=2),
            ContentType='application/json'
        )
        
    except Exception as e:
        print(f"Error storing daily analysis: {e}")

def send_comprehensive_email_notification(ses, recipient, analysis, function_type):
    """Send comprehensive email notification for all function executions"""
    try:
        signals = [r for r in analysis.get('results', []) if r.get('signal', {}).get('action') != 'HOLD']
        
        # Function-specific subject and header
        if function_type == 'sentiment-enhanced':
            subject = f"🤖 Sentiment-Enhanced Trading Analysis - {analysis.get('date', 'N/A')}"
            header = "SENTIMENT-ENHANCED SWING TRADING ANALYSIS"
        elif function_type == 'performance':
            subject = f"📈 Performance Analysis Report - {analysis.get('date', 'N/A')}"
            header = "PERFORMANCE ANALYSIS REPORT"
        else:
            subject = f"📉 Main Trading Analysis - {analysis.get('date', 'N/A')}"
            header = "MAIN SWING TRADING ANALYSIS"
        
        body = f"""
{header}
{'='*60}
Function: {function_type.upper()}
Date: {analysis.get('date', 'N/A')}
Time: {analysis.get('timestamp', 'N/A')}
Status: COMPLETED SUCCESSFULLY

"""
        
        # Add function-specific content
        if function_type == 'sentiment-enhanced':
            body += f"""
SYMBOLS ANALYZED: {analysis.get('symbols_analyzed', 0)}
SIGNALS GENERATED: {analysis.get('signals_generated', 0)}

DETAILED ANALYSIS:
{'-'*40}
"""
            
            for result in analysis.get('results', []):
                sentiment = result.get('sentiment', {})
                signal = result.get('signal', {})
                
                body += f"""
{result['symbol']}: {signal.get('action', 'N/A')} ({signal.get('strength', 'N/A')})
  Price: ${result.get('price', 0):.2f} | RSI: {result.get('rsi', 0)} | EMA: ${result.get('ema', 0):.2f}
  Sentiment: {sentiment.get('overall_score', 0)} (Confidence: {sentiment.get('confidence', 0):.1%})
  Sources: {', '.join(sentiment.get('sources', {}).keys()) or 'None'}
  Reasoning: {signal.get('reasoning', 'N/A')}
"""
                
        elif function_type == 'performance':
            body += f"""
PERFORMANCE METRICS:
{'-'*40}
Analysis Period: {analysis.get('days_back', 'N/A')} days
Total Signals: {analysis.get('total_signals', 0)}
Successful Signals: {analysis.get('successful_signals', 0)}
Success Rate: {analysis.get('success_rate', 0):.1%}
Total P&L: ${analysis.get('total_pnl', 0):.2f}

DETAILS:
{analysis.get('summary', 'No detailed analysis available')}
"""
        
        else:  # main function
            body += f"""
SYMBOLS ANALYZED: {analysis.get('symbols_analyzed', 0)}
SIGNALS GENERATED: {analysis.get('signals_generated', 0)}

DETAILED ANALYSIS:
{'-'*40}
"""
            
            for result in analysis.get('results', []):
                signal = result.get('signal', {})
                
                body += f"""
{result['symbol']}: {signal.get('action', 'N/A')} ({signal.get('strength', 'N/A')})
  Price: ${result.get('price', 0):.2f} | RSI: {result.get('rsi', 0)} | EMA: ${result.get('ema', 0):.2f}
  Technical: {signal.get('reasoning', 'N/A')}
"""
        
        body += f"""

{'='*60}
AWS SWING TRADING AUTOMATION SYSTEM
Function: {function_type.upper()}
Execution Time: {analysis.get('timestamp', 'N/A')}
Next Scheduled Run: Check EventBridge schedules
{'='*60}
"""
        
        ses.send_email(
            Source=recipient,
            Destination={'ToAddresses': [recipient]},
            Message={
                'Subject': {'Data': subject},
                'Body': {'Text': {'Data': body}}
            }
        )
        
        print(f"Comprehensive email sent successfully for {function_type} function")
        
    except Exception as e:
        print(f"Error sending comprehensive email: {e}")