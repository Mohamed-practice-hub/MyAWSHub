import boto3
import json
import requests
from datetime import datetime, timedelta

# Initialize clients
s3_client = boto3.client('s3')
S3_BUCKET = 'swing-automation-data-processor'

def get_alpaca_keys():
    """Retrieve Alpaca API keys from AWS Secrets Manager"""
    client = boto3.client('secretsmanager')
    secret_name = "swing-alpaca/papter-trading/keys"
    response = client.get_secret_value(SecretId=secret_name)
    secret = json.loads(response['SecretString'])
    return secret['ALPACA_API_KEY'], secret['ALPACA_SECRET_KEY']

API_KEY, SECRET_KEY = get_alpaca_keys()
HEADERS = {
    "APCA-API-KEY-ID": API_KEY,
    "APCA-API-SECRET-KEY": SECRET_KEY
}

def get_s3_signals(days_back=30):
    """Get all BUY/SELL signals from the last N days"""
    print(f"📊 Fetching signals from last {days_back} days...")
    signals = []
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    try:
        # List objects in signals folder
        response = s3_client.list_objects_v2(
            Bucket=S3_BUCKET,
            Prefix='signals/',
            StartAfter=f'signals/{start_date.strftime("%Y/%m")}/'
        )
        
        for obj in response.get('Contents', []):
            # Get signal file
            file_response = s3_client.get_object(Bucket=S3_BUCKET, Key=obj['Key'])
            file_content = json.loads(file_response['Body'].read())
            signals.extend(file_content)
    
    except Exception as e:
        print(f"❌ Error fetching signals: {e}")
    
    print(f"✅ Found {len(signals)} signals to analyze")
    return signals

def get_current_price(symbol):
    """Get current price for a symbol"""
    url = f"https://data.alpaca.markets/v2/stocks/{symbol}/bars"
    params = {"timeframe": "1Day", "limit": 1}
    
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        data = response.json()
        bars = data.get('bars', [])
        if bars:
            return float(bars[0]['c'])
    except Exception as e:
        print(f"❌ Error getting price for {symbol}: {e}")
    
    return None

def analyze_signal_performance(signals):
    """Analyze how well each signal performed"""
    print("🔍 Analyzing signal performance...")
    results = []
    
    for signal in signals:
        symbol = signal['symbol']
        signal_type = signal['signal']
        signal_price = signal['current_price']
        signal_date = signal['timestamp']
        
        print(f"📈 Analyzing {symbol} {signal_type} signal from {signal_date}")
        
        # Get current price
        current_price = get_current_price(symbol)
        if not current_price:
            continue
        
        # Calculate performance
        if signal_type == 'BUY':
            # For BUY signals, profit if price went up
            price_change = current_price - signal_price
            profit_pct = (price_change / signal_price) * 100
            success = price_change > 0
        else:  # SELL
            # For SELL signals, profit if price went down
            price_change = signal_price - current_price
            profit_pct = (price_change / signal_price) * 100
            success = price_change > 0
        
        result = {
            'symbol': symbol,
            'signal': signal_type,
            'signal_date': signal_date,
            'signal_price': signal_price,
            'current_price': current_price,
            'price_change': round(price_change, 2),
            'profit_percentage': round(profit_pct, 2),
            'success': success,
            'days_held': (datetime.now() - datetime.fromisoformat(signal_date.replace('Z', '+00:00'))).days
        }
        
        results.append(result)
        
        status = "✅ SUCCESS" if success else "❌ LOSS"
        print(f"   {status}: {profit_pct:+.2f}% ({price_change:+.2f})")
    
    return results

def generate_performance_report(results):
    """Generate comprehensive performance report"""
    if not results:
        return "No signals to analyze"
    
    # Calculate overall statistics
    total_signals = len(results)
    successful_signals = len([r for r in results if r['success']])
    success_rate = (successful_signals / total_signals) * 100
    
    avg_profit = sum([r['profit_percentage'] for r in results]) / total_signals
    
    buy_signals = [r for r in results if r['signal'] == 'BUY']
    sell_signals = [r for r in results if r['signal'] == 'SELL']
    
    buy_success_rate = (len([r for r in buy_signals if r['success']]) / len(buy_signals) * 100) if buy_signals else 0
    sell_success_rate = (len([r for r in sell_signals if r['success']]) / len(sell_signals) * 100) if sell_signals else 0
    
    # Generate report
    report = f"""
🎯 SWING TRADING BOT PERFORMANCE REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📊 OVERALL PERFORMANCE:
• Total Signals: {total_signals}
• Successful Signals: {successful_signals}
• Success Rate: {success_rate:.1f}%
• Average Profit/Loss: {avg_profit:+.2f}%

📈 SIGNAL BREAKDOWN:
• BUY Signals: {len(buy_signals)} (Success Rate: {buy_success_rate:.1f}%)
• SELL Signals: {len(sell_signals)} (Success Rate: {sell_success_rate:.1f}%)

🏆 TOP PERFORMERS:
"""
    
    # Sort by profit percentage
    top_performers = sorted(results, key=lambda x: x['profit_percentage'], reverse=True)[:5]
    for i, result in enumerate(top_performers, 1):
        report += f"{i}. {result['symbol']} {result['signal']}: {result['profit_percentage']:+.2f}% ({result['days_held']} days)\n"
    
    report += "\n💸 WORST PERFORMERS:\n"
    worst_performers = sorted(results, key=lambda x: x['profit_percentage'])[:5]
    for i, result in enumerate(worst_performers, 1):
        report += f"{i}. {result['symbol']} {result['signal']}: {result['profit_percentage']:+.2f}% ({result['days_held']} days)\n"
    
    report += "\n📋 DETAILED RESULTS:\n"
    for result in sorted(results, key=lambda x: x['signal_date'], reverse=True):
        status = "✅" if result['success'] else "❌"
        report += f"{status} {result['symbol']} {result['signal']} | {result['profit_percentage']:+.2f}% | {result['signal_date'][:10]}\n"
    
    return report

def lambda_handler(event, context):
    """Main performance analyzer handler"""
    print("🎯 Starting performance analysis...")
    
    # Get analysis period (default 30 days)
    days_back = event.get('days_back', 30)
    
    # Fetch signals from S3
    signals = get_s3_signals(days_back)
    
    if not signals:
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'No signals found to analyze'})
        }
    
    # Analyze performance
    results = analyze_signal_performance(signals)
    
    # Generate report
    report = generate_performance_report(results)
    print(report)
    
    # Save performance report to S3
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_filename = f"performance-reports/performance_report_{timestamp}.txt"
    
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=report_filename,
            Body=report,
            ContentType='text/plain'
        )
        print(f"✅ Performance report saved: {report_filename}")
    except Exception as e:
        print(f"❌ Error saving report: {e}")
    
    # Save detailed results as JSON
    results_filename = f"performance-reports/performance_data_{timestamp}.json"
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=results_filename,
            Body=json.dumps(results, indent=2),
            ContentType='application/json'
        )
        print(f"✅ Performance data saved: {results_filename}")
    except Exception as e:
        print(f"❌ Error saving data: {e}")
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': f'Analyzed {len(results)} signals',
            'success_rate': f"{(len([r for r in results if r['success']]) / len(results) * 100):.1f}%" if results else "0%",
            'report_location': report_filename
        })
    }