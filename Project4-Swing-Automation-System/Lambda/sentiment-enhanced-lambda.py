import boto3
    body = []
    body.append("🎯 SWING TRADING BOT - SENTIMENT-ENHANCED SIGNALS")
    body.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {DEFAULT_TZ}")
    body.append("")
    body.append("SIGNAL SUMMARY:")
    body.append(f"  Total Signals: {len(signals)}")
    body.append(f"  Strong: {len([s for s in signals if s['signal_strength'] == 'STRONG'])} | Moderate: {len([s for s in signals if s['signal_strength'] == 'MODERATE'])} | Weak: {len([s for s in signals if s['signal_strength'] == 'WEAK'])}")
    body.append("")
    body.append("ACTIVE SIGNALS (fixed-width columns):")
    # Table header
    header = f"{'SYMBOL':<8} {'SIGNAL':<12} {'STRENGTH':<10} {'PRICE':>10} {'RSI':>6} {'SENTIMENT':>10} {'CONF':>6}"
    body.append(header)
    body.append('-' * len(header))

    for result in signals:
        sym = result['symbol']
        sig = result['signal']
        strength = result['signal_strength']
        price = f"${result['current_price']:.2f}"
        rsi = f"{result['rsi']:.1f}"
        sent = f"{result['sentiment_score']:.3f}"
        conf = f"{result['sentiment_confidence']:.2f}"
        row = f"{sym:<8} {sig:<12} {strength:<10} {price:>10} {rsi:>6} {sent:>10} {conf:>6}"
        body.append(row)

    body.append("")
    body.append("SENTIMENT BREAKDOWN:")
    try:
        if ZoneInfo is not None:
            return datetime.now(ZoneInfo(DEFAULT_TZ)).strftime('%Y-%m-%d %H:%M:%S %Z')
    except Exception:
        pass
    # fallback to UTC if zoneinfo not available
    return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')

def log(message, level='INFO'):
    # include request id if available in global
    req = getattr(log, 'request_id', 'N/A')
    ts = _get_now_tz()
    print(f"{ts} [{level}] request_id={req} - {message}")

def get_all_secrets():
    """Retrieve all API keys from AWS Secrets Manager"""
    secret_name = "swing-alpaca/papter-trading/keys"
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        print(f"❌ Error retrieving secrets: {e}")
        return {}

def rate_limit_sleep(calls_per_minute=50):
    """Simple rate limiting"""
    time.sleep(60 / calls_per_minute)

def get_multi_source_sentiment(symbol, api_keys):
    """Combine sentiment from multiple free sources"""
    print(f"🔍 Fetching sentiment for {symbol} from multiple sources...")
    sentiments = []
    weights = []
    source_details = {}
    
    # 1. Finnhub (Weight: 50% - Most reliable)
    try:
        print(f"📰 Fetching Finnhub sentiment for {symbol}...")
        url = f"https://finnhub.io/api/v1/news-sentiment?symbol={symbol}&token={api_keys.get('FINNHUB_API_KEY')}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'sentiment' in data and 'companyNewsScore' in data['sentiment']:
                sentiment_score = data['sentiment']['companyNewsScore']
                sentiments.append(sentiment_score)
                weights.append(0.5)
                source_details['finnhub'] = {
                    'score': sentiment_score,
                    'weight': 0.5,
                    'articles_count': data['sentiment'].get('articlesInLastWeek', 0)
                }
                print(f"✅ Finnhub sentiment: {sentiment_score:.3f}")
            else:
                print("⚠️ Finnhub: No sentiment data available")
        else:
            print(f"❌ Finnhub API error: {response.status_code}")
        rate_limit_sleep(50)  # Respect rate limits
    except Exception as e:
        print(f"❌ Finnhub error: {e}")
    
    # 2. NewsAPI + Simple NLP (Weight: 35%)
    try:
        print(f"📰 Fetching NewsAPI sentiment for {symbol}...")
        url = f"https://newsapi.org/v2/everything?q={symbol}&apiKey={api_keys.get('NEWSAPI_KEY')}&pageSize=20&sortBy=publishedAt"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'articles' in data and data['articles']:
                news_sentiment = analyze_news_sentiment(data['articles'])
                sentiments.append(news_sentiment)
                weights.append(0.35)
                source_details['newsapi'] = {
                    'score': news_sentiment,
                    'weight': 0.35,
                    'articles_count': len(data['articles'])
                }
                print(f"✅ NewsAPI sentiment: {news_sentiment:.3f}")
            else:
                print("⚠️ NewsAPI: No articles found")
        else:
            print(f"❌ NewsAPI error: {response.status_code}")
        rate_limit_sleep(60)  # NewsAPI rate limit
    except Exception as e:
        print(f"❌ NewsAPI error: {e}")
    
    # 3. Reddit Sentiment (Weight: 15%)
    try:
        print(f"🔍 Fetching Reddit sentiment for {symbol}...")
        reddit_sentiment = get_reddit_sentiment(symbol, api_keys)
        if reddit_sentiment is not None:
            sentiments.append(reddit_sentiment)
            weights.append(0.15)
            source_details['reddit'] = {
                'score': reddit_sentiment,
                'weight': 0.15,
                'posts_analyzed': 10  # Placeholder
            }
            print(f"✅ Reddit sentiment: {reddit_sentiment:.3f}")
        else:
            print("⚠️ Reddit: No sentiment data available")
    except Exception as e:
        print(f"❌ Reddit error: {e}")
    
    # Calculate weighted average
    if sentiments:
        weighted_sentiment = sum(s * w for s, w in zip(sentiments, weights)) / sum(weights)
        confidence = len(sentiments) / 3  # Confidence based on source availability (3 sources max)
        print(f"📊 Combined sentiment: {weighted_sentiment:.3f} (confidence: {confidence:.2f})")
        return weighted_sentiment, confidence, source_details
    
    print("⚠️ No sentiment data available from any source")
    return 0, 0, {}  # Neutral sentiment, no confidence

def analyze_news_sentiment(articles):
    """Enhanced keyword-based sentiment analysis"""
    positive_words = [
        'growth', 'profit', 'gain', 'rise', 'bull', 'strong', 'beat', 'exceed',
        'upgrade', 'outperform', 'buy', 'positive', 'surge', 'rally', 'boom',
        'success', 'breakthrough', 'expansion', 'revenue', 'earnings'
    ]
    negative_words = [
        'loss', 'drop', 'fall', 'bear', 'weak', 'miss', 'decline', 'crash',
        'downgrade', 'underperform', 'sell', 'negative', 'plunge', 'slump',
        'recession', 'bankruptcy', 'lawsuit', 'investigation', 'scandal'
    ]
    
    sentiment_scores = []
    for article in articles[:20]:  # Analyze top 20 articles
        title = article.get('title', '').lower()
        description = article.get('description', '').lower()
        text = f"{title} {description}"
        
        positive_count = sum(1 for word in positive_words if word in text)
        negative_count = sum(1 for word in negative_words if word in text)
        
        if positive_count + negative_count > 0:
            article_sentiment = (positive_count - negative_count) / (positive_count + negative_count)
            sentiment_scores.append(article_sentiment)
    
    return np.mean(sentiment_scores) if sentiment_scores else 0

def get_reddit_sentiment(symbol, api_keys):
    """Get sentiment from Reddit discussions"""
    try:
        # Reddit OAuth2 authentication
        client_id = api_keys.get('REDDIT_CLIENT_ID')
        client_secret = api_keys.get('REDDIT_CLIENT_SECRET')
        
        if not client_id or not client_secret:
            print("⚠️ Reddit credentials not found")
            return None
        
        # Get OAuth token
        auth = requests.auth.HTTPBasicAuth(client_id, client_secret)
        data = {
            'grant_type': 'client_credentials',
            'username': 'swing-trading-bot',
            'password': 'dummy'
        }
        headers = {'User-Agent': 'SwingTradingBot/1.0'}
        
        response = requests.post('https://www.reddit.com/api/v1/access_token',
                               auth=auth, data=data, headers=headers, timeout=10)
        
        if response.status_code != 200:
            print(f"❌ Reddit auth failed: {response.status_code}")
            return None
        
        token = response.json()['access_token']
        headers['Authorization'] = f'bearer {token}'
        
        # Search for symbol mentions in investing subreddits
        subreddits = ['stocks', 'investing', 'SecurityAnalysis', 'ValueInvesting']
        sentiment_scores = []
        
        for subreddit in subreddits:
            search_url = f'https://oauth.reddit.com/r/{subreddit}/search'
            params = {
                'q': symbol,
                'sort': 'new',
                'limit': 10,
                'restrict_sr': 'true'
            }
            
            response = requests.get(search_url, headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                posts = response.json().get('data', {}).get('children', [])
                for post in posts:
                    title = post['data'].get('title', '').lower()
                    selftext = post['data'].get('selftext', '').lower()
                    text = f"{title} {selftext}"
                    
                    # Simple sentiment analysis on Reddit posts
                    positive_words = ['bullish', 'buy', 'long', 'moon', 'rocket', 'gains']
                    negative_words = ['bearish', 'sell', 'short', 'crash', 'dump', 'loss']
                    
                    pos_count = sum(1 for word in positive_words if word in text)
                    neg_count = sum(1 for word in negative_words if word in text)
                    
                    if pos_count + neg_count > 0:
                        sentiment_scores.append((pos_count - neg_count) / (pos_count + neg_count))
            
            time.sleep(1)  # Rate limiting
        
        return np.mean(sentiment_scores) if sentiment_scores else 0
        
    except Exception as e:
        print(f"❌ Reddit sentiment error: {e}")
        return None



def get_stock_data(symbol, api_key, secret_key):
    """Get current stock price and calculate technical indicators"""
    headers = {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": secret_key
    }
    
    # Get current price
    url = f"https://data.alpaca.markets/v2/stocks/{symbol}/bars"
    params = {
        "timeframe": "1Day",
        "limit": 50,
        "asof": datetime.now().strftime('%Y-%m-%d')
    }
    
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        print(f"❌ Error fetching data for {symbol}: {response.status_code}")
        return None
    
    data = response.json()
    bars = data.get('bars', [])
    
    if not bars:
        print(f"❌ No data available for {symbol}")
        return None

    # Persist raw bars to S3 for auditing and historical analysis
    try:
        s3_key = f"historical/{symbol}/{datetime.utcnow().strftime('%Y/%m/%d')}/bars_{datetime.utcnow().strftime('%H%M%S')}.json"
        s3_client.put_object(Bucket=os.environ.get('BUCKET_NAME', 'swing-automation-data-processor'), Key=s3_key, Body=json.dumps(bars), ContentType='application/json')
        print(f"Saved historical bars to s3://{os.environ.get('BUCKET_NAME', 'swing-automation-data-processor')}/{s3_key}")
    except Exception as e:
        print(f"⚠️ Unable to save bars to S3: {e}")
    
    # If pandas is available, use DataFrame convenience. Otherwise compute manually.
    try:
        if PANDAS_AVAILABLE and pd is not None:
            df = pd.DataFrame(bars)
            df['timestamp'] = pd.to_datetime(df['t'])
            df = df.sort_values('timestamp')
            # Calculate technical indicators
            df['rsi'] = calculate_rsi(df['c'].values)
            df['ema_12'] = df['c'].ewm(span=12).mean()
            df['ema_26'] = df['c'].ewm(span=26).mean()
            latest = df.iloc[-1]
            return {
                'symbol': symbol,
                'current_price': float(latest['c']),
                'rsi': float(latest['rsi']),
                'ema_12': float(latest['ema_12']),
                'ema_26': float(latest['ema_26']),
                'volume': int(latest['v']),
                'timestamp': latest['timestamp'].isoformat()
            }
        else:
            # Manual computation using lists and numpy
            prices = [float(bar['c']) for bar in bars]
            timestamps = [bar.get('t') for bar in bars]
            prices = prices[::-1] if False else prices  # ensure chronological if needed

            # RSI array
            rsi_array = calculate_rsi(prices)

            # Simple EMA helper
            def calc_ema(prices_list, period):
                ema = prices_list[0]
                multiplier = 2 / (period + 1)
                for p in prices_list[1:]:
                    ema = (p - ema) * multiplier + ema
                return ema

            ema_12 = calc_ema(prices, 12)
            ema_26 = calc_ema(prices, 26)

            latest_idx = -1
            return {
                'symbol': symbol,
                'current_price': float(prices[latest_idx]),
                'rsi': float(rsi_array[latest_idx]) if len(rsi_array) > 0 else 50.0,
                'ema_12': float(ema_12),
                'ema_26': float(ema_26),
                'volume': int(bars[latest_idx].get('v', 0)),
                'timestamp': datetime.utcnow().isoformat()
            }
    except Exception as e:
        print(f"❌ Error computing technicals for {symbol}: {e}")
        return None

def calculate_rsi(prices, period=14):
    """Calculate RSI indicator"""
    prices = np.array(prices)
    deltas = np.diff(prices)
    seed = deltas[:period+1]
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period
    rs = up / down if down != 0 else 0
    rsi = np.zeros_like(prices)
    rsi[:period] = 100. - 100. / (1. + rs)
    
    for i in range(period, len(prices)):
        delta = deltas[i-1]
        if delta > 0:
            upval = delta
            downval = 0.
        else:
            upval = 0.
            downval = -delta
        
        up = (up * (period - 1) + upval) / period
        down = (down * (period - 1) + downval) / period
        rs = up / down if down != 0 else 0
        rsi[i] = 100. - 100. / (1. + rs)
    
    return rsi

def enhanced_signal_analysis(stock_data, sentiment_score, confidence, source_details):
    """Enhanced signal analysis with sentiment integration"""
    symbol = stock_data['symbol']
    price = stock_data['current_price']
    rsi = stock_data['rsi']
    ema_12 = stock_data['ema_12']
    ema_26 = stock_data['ema_26']
    
    print(f"📊 Analyzing {symbol}: Price=${price:.2f}, RSI={rsi:.1f}, EMA12=${ema_12:.2f}, EMA26=${ema_26:.2f}")
    print(f"💭 Sentiment: {sentiment_score:.3f} (confidence: {confidence:.2f})")
    
    # Original technical signals
    technical_buy = rsi < 30 and price > ema_12
    technical_sell = rsi > 70 and price < ema_12
    
    # Sentiment-enhanced signals (3 sources max)
    if confidence >= 0.67:  # High confidence (2+ sources)
        sentiment_threshold_buy = 0.2
        sentiment_threshold_sell = -0.2
    elif confidence >= 0.33:  # Medium confidence (1+ sources)
        sentiment_threshold_buy = 0.3
        sentiment_threshold_sell = -0.3
    else:  # Low confidence (fallback)
        sentiment_threshold_buy = 0.4
        sentiment_threshold_sell = -0.4
    
    sentiment_buy = sentiment_score > sentiment_threshold_buy
    sentiment_sell = sentiment_score < sentiment_threshold_sell
    
    # Combined signal logic
    signal = "HOLD"
    signal_strength = "NONE"
    reasoning = []
    
    if technical_buy and sentiment_buy:
        signal = "BUY"
        if confidence >= 0.67 and sentiment_score > 0.4:
            signal_strength = "STRONG"
        elif confidence >= 0.33:
            signal_strength = "MODERATE"
        else:
            signal_strength = "WEAK"
        reasoning.append(f"Technical BUY (RSI={rsi:.1f}<30, Price>${price:.2f}>EMA12${ema_12:.2f})")
        reasoning.append(f"Sentiment BUY (score={sentiment_score:.3f}>{sentiment_threshold_buy}, confidence={confidence:.2f})")
    
    elif technical_sell and sentiment_sell:
        signal = "SELL"
        if confidence >= 0.67 and sentiment_score < -0.4:
            signal_strength = "STRONG"
        elif confidence >= 0.33:
            signal_strength = "MODERATE"
        else:
            signal_strength = "WEAK"
        reasoning.append(f"Technical SELL (RSI={rsi:.1f}>70, Price>${price:.2f}<EMA12${ema_12:.2f})")
        reasoning.append(f"Sentiment SELL (score={sentiment_score:.3f}<{sentiment_threshold_sell}, confidence={confidence:.2f})")
    
    elif technical_buy or technical_sell:
        # Technical signal without sentiment confirmation
        if technical_buy:
            signal = "WEAK_BUY"
            reasoning.append("Technical BUY without sentiment confirmation")
        else:
            signal = "WEAK_SELL"
            reasoning.append("Technical SELL without sentiment confirmation")
        signal_strength = "WEAK"
    
    return {
        'symbol': symbol,
        'signal': signal,
        'signal_strength': signal_strength,
        'current_price': price,
        'rsi': rsi,
        'ema_12': ema_12,
        'ema_26': ema_26,
        'sentiment_score': sentiment_score,
        'sentiment_confidence': confidence,
        'sentiment_sources': source_details,
        'reasoning': reasoning,
        'timestamp': datetime.now().isoformat()
    }

def save_to_s3(data, bucket, key):
    """Save data to S3"""
    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(data, indent=2),
            ContentType='application/json'
        )
        print(f"✅ Saved to S3: s3://{bucket}/{key}")
    except Exception as e:
        print(f"❌ Error saving to S3: {e}")

def send_email_notification(analysis_results, recipient_email):
    """Send enhanced email notification with sentiment analysis"""
    signals = [r for r in analysis_results if r['signal'] != 'HOLD']
    
    if not signals:
        print("📧 No signals to report")
        return
    
    subject = f"🎯 Swing Trading Signals - {len(signals)} Alert(s) - {datetime.now().strftime('%Y-%m-%d')}"
    
    body = f"""
🎯 SWING TRADING BOT - SENTIMENT-ENHANCED SIGNALS
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ET

📊 SIGNAL SUMMARY:
• Total Signals: {len(signals)}
• Strong Signals: {len([s for s in signals if s['signal_strength'] == 'STRONG'])}
• Moderate Signals: {len([s for s in signals if s['signal_strength'] == 'MODERATE'])}
• Weak Signals: {len([s for s in signals if s['signal_strength'] == 'WEAK'])}

🚨 ACTIVE SIGNALS:
"""
    
    for result in signals:
        strength_emoji = {"STRONG": "🔥", "MODERATE": "⚡", "WEAK": "💡"}.get(result['signal_strength'], "")
        signal_emoji = {"BUY": "🟢", "SELL": "🔴", "WEAK_BUY": "🟡", "WEAK_SELL": "🟠"}.get(result['signal'], "")
        
        body += f"""
{signal_emoji} {result['symbol']} - {result['signal']} {strength_emoji}
• Price: ${result['current_price']:.2f}
• RSI: {result['rsi']:.1f}
• Sentiment: {result['sentiment_score']:.3f} (confidence: {result['sentiment_confidence']:.2f})
• Sources: {len(result['sentiment_sources'])} active
• Reasoning: {'; '.join(result['reasoning'])}

"""
    
    body += f"""
📈 SENTIMENT BREAKDOWN:
"""
    
    for result in signals:
        if result['sentiment_sources']:
            body += f"\n{result['symbol']} Sentiment Sources:\n"
            for source, details in result['sentiment_sources'].items():
                body += f"• {source.title()}: {details['score']:.3f} (weight: {details['weight']:.1%})\n"
    
    body += f"""

⚠️ DISCLAIMER:
This is an automated analysis for educational purposes only.
Not financial advice. Always do your own research.

📊 System Status: Sentiment-Enhanced Analysis Active
🔗 Data Sources: Alpaca Markets + Multi-Source Sentiment Analysis
"""
    
    try:
        ses_client.send_email(
            Source=os.environ.get('EMAIL_SOURCE', 'mhussain.myindia@gmail.com'),
            Destination={'ToAddresses': [recipient_email]},
            Message={
                'Subject': {'Data': subject},
                'Body': {'Text': {'Data': body}}
            }
        )
        print(f"✅ Email sent to {recipient_email}")
    except Exception as e:
        print(f"❌ Error sending email: {e}")

def lambda_handler(event, context):
    """Enhanced Lambda handler with sentiment analysis"""
    log("🚀 Starting sentiment-enhanced swing trading analysis...")
    # attach request id for subsequent log lines
    try:
        log.request_id = getattr(context, 'aws_request_id', 'N/A')
    except Exception:
        log.request_id = 'N/A'
    # Get configuration from environment variables
    bucket_name = os.environ.get('BUCKET_NAME', 'swing-automation-data-processor')
    email_recipient = os.environ.get('EMAIL_RECIPIENT', os.environ.get('EMAIL_SOURCE', 'mhussain.myindia@gmail.com'))
    symbols = event.get('symbols', ['AAPL', 'NVDA', 'MSFT', 'AMD', 'TSLA', 'ARKK', 'BOTZ', 'QQQ'])
    mode = event.get('mode', 'run')  # 'run' or 'check'
    
    # Get all API keys
    api_keys = get_all_secrets()
    if not api_keys:
        log('Failed to retrieve API keys', level='ERROR')
        return {'statusCode': 500, 'body': 'Failed to retrieve API keys'}
    
    alpaca_api_key = api_keys.get('ALPACA_API_KEY')
    alpaca_secret_key = api_keys.get('ALPACA_SECRET_KEY')
    
    if not alpaca_api_key or not alpaca_secret_key:
        return {'statusCode': 500, 'body': 'Alpaca API keys not found'}
    
    # If running in 'check' mode, verify S3 daily-analysis for today's date and alert if missing
    if mode == 'check':
        today_prefix = f"daily-analysis/{datetime.now().strftime('%Y/%m/%d')}/"
        try:
            resp = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=today_prefix, MaxKeys=1)
            if 'Contents' in resp and resp['KeyCount'] > 0:
                log(f"Daily analysis found for today under {today_prefix}")
                return {'statusCode': 200, 'body': 'Daily analysis exists'}
            else:
                # Send alert email
                alert_body = f"Alert: No daily analysis files found in s3://{bucket_name}/{today_prefix}"
                try:
                    ses_client.send_email(
                        Source=os.environ.get('EMAIL_SOURCE', 'mhussain.myindia@gmail.com'),
                        Destination={'ToAddresses': [email_recipient]},
                        Message={
                            'Subject': {'Data': f"⚠️ Missing daily analysis - {datetime.now().strftime('%Y-%m-%d') }"},
                            'Body': {'Text': {'Data': alert_body}}
                        }
                    )
                    log(f"Missing-file alert sent to {email_recipient}")
                except Exception as e:
                    log(f"Error sending missing-file alert: {e}", level='ERROR')
                return {'statusCode': 200, 'body': 'Missing daily analysis - alert sent'}
        except Exception as e:
            log(f"Error checking S3 for daily analysis: {e}", level='ERROR')
            return {'statusCode': 500, 'body': 'Error checking S3'}

    analysis_results = []
    
    for symbol in symbols:
        log(f"Analyzing {symbol}...")
        
        # Get stock data
        stock_data = get_stock_data(symbol, alpaca_api_key, alpaca_secret_key)
        if not stock_data:
            log(f"No stock data for {symbol}, skipping", level='WARNING')
            continue
        
        # Get multi-source sentiment
        sentiment_score, confidence, source_details = get_multi_source_sentiment(symbol, api_keys)
        
        # Perform enhanced analysis
        result = enhanced_signal_analysis(stock_data, sentiment_score, confidence, source_details)
        analysis_results.append(result)
        log(f"{symbol}: {result['signal']} ({result['signal_strength']})")

        # Rate limiting between symbols
        time.sleep(2)
    
    # Save results to S3
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save daily analysis
    daily_key = f"daily-analysis/{datetime.now().strftime('%Y/%m/%d')}/sentiment_analysis_{timestamp}.json"
    save_to_s3(analysis_results, bucket_name, daily_key)
    log(f"Saved daily analysis to {daily_key}")
    
    # Save signals only
    signals = [r for r in analysis_results if r['signal'] != 'HOLD']
    if signals:
        signals_key = f"signals/{datetime.now().strftime('%Y/%m/%d')}/sentiment_signals_{timestamp}.json"
        save_to_s3(signals, bucket_name, signals_key)
    
    # Send email notification
    send_email_notification(analysis_results, email_recipient)
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': f'Analyzed {len(symbols)} symbols with sentiment enhancement',
            'signals_found': len(signals),
            'analysis_timestamp': timestamp
        })
    }