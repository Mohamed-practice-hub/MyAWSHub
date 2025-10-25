#!/usr/bin/env bash
SYMBOL=${1:-TEST_SYNC}
TABLENAME=${2:-tradebot_signals_table}
OPEN=${3:-100}
HIGH=${4:-110}
LOW=${5:-90}
CLOSE=${6:-105}
VOLUME=${7:-1000}

NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
TRADEDATE=$(date +%Y-%m-%d)
TF=tmp_test_sync_item.json
cat > $TF <<EOF
{
  "SymbolKey": { "S": "$SYMBOL"},
  "TradedDate": { "S": "$TRADEDATE"},
  "Open": { "N": "$OPEN"},
  "High": { "N": "$HIGH"},
  "Low": { "N": "$LOW"},
  "Close": { "N": "$CLOSE"},
  "Volume": { "N": "$VOLUME"},
  "Timestamp": { "S":"$NOW"}
}
EOF

aws dynamodb put-item --table-name $TABLENAME --item file://$TF --region us-east-1
echo "Inserted test item for $SYMBOL with TradedDate $TRADEDATE and Timestamp $NOW"
rm -f $TF
