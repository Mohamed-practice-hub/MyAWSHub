package com.tradebot.analysis;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.dynamodb.DynamoDbClient;
import software.amazon.awssdk.services.dynamodb.model.AttributeValue;
import software.amazon.awssdk.services.dynamodb.model.QueryRequest;
import software.amazon.awssdk.services.dynamodb.model.QueryResponse;
import software.amazon.awssdk.services.dynamodb.model.UpdateItemRequest;
import software.amazon.awssdk.services.ses.SesClient;
import software.amazon.awssdk.services.ses.model.Body;
import software.amazon.awssdk.services.ses.model.Content;
import software.amazon.awssdk.services.ses.model.Destination;
import software.amazon.awssdk.services.ses.model.Message;
import software.amazon.awssdk.services.ses.model.SendEmailRequest;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.*;
import java.util.stream.Collectors;

public class AnalysisHandler implements RequestHandler<Map<String,Object>, Map<String,Object>> {
    private static final Logger logger = LoggerFactory.getLogger(AnalysisHandler.class);
    private final String tableName;
    private final Region region;
    private final DynamoDbClient dynamo;
    private final SesClient sesClient;

    public AnalysisHandler() {
        String regionEnv = System.getenv().getOrDefault("AWS_REGION", "us-east-1");
        this.region = Region.of(regionEnv);
        this.dynamo = DynamoDbClient.builder().region(region).build();
        this.sesClient = SesClient.builder().region(region).build();
        this.tableName = System.getenv().getOrDefault("DYNAMODB_TABLE", "tradebot_signals_table");
    }

    @Override
    public Map<String, Object> handleRequest(Map<String, Object> event, Context context) {
        logger.info("Received event: {}", event);
        Map<String,Object> resp = new HashMap<>();
        if (event == null) {
            resp.put("status", "no_event");
            return resp;
        }

        // Test notification
        if (event.containsKey("test_notification")) {
            String msg = String.valueOf(event.getOrDefault("test_message", "Test notification from analysis lambda"));
            notifyTelegram("[TEST] " + msg);
            notifyEmail("Test notification from analysis lambda", msg);
            resp.put("status", "test_sent");
            return resp;
        }

        // Backfill and always override DB values
        if (event.containsKey("backfilldays") && event.containsKey("symbols")) {
            int backfillDays = ((Number)event.getOrDefault("backfilldays", 1)).intValue();
            List<String> symbols = extractSymbols(event);
            logger.info("Running backfill for symbols={} days={}", symbols, backfillDays);
            Map<String,Integer> results = new HashMap<>();
            for (String symbol : symbols) {
                int updated = backfillSymbolAlwaysOverride(symbol, backfillDays);
                results.put(symbol, updated);
            }
            resp.put("status", "backfill_done");
            resp.put("results", results);
            return resp;
        }

        // DynamoDB stream-style record(s)
        if (event.containsKey("Records")) {
            List<?> raw = (List<?>) event.get("Records");
            for (Object r : raw) {
                if (!(r instanceof Map)) continue;
                Map<?,?> rec = (Map<?,?>) r;
                String eventSource = String.valueOf(rec.getOrDefault("eventSource", ""));
                Object dynamoObj = rec.get("dynamodb");
                if (!(dynamoObj instanceof Map)) {
                    logger.warn("Skipping record: 'dynamodb' field is not a Map, got {}", dynamoObj == null ? "null" : dynamoObj.getClass().getName());
                    continue;
                }
                Map<?,?> dynamoRec = (Map<?,?>) dynamoObj;
                Object newImageObj = dynamoRec.get("NewImage");
                if (!(newImageObj instanceof Map)) {
                    logger.warn("Skipping record: 'NewImage' field is not a Map, got {}", newImageObj == null ? "null" : newImageObj.getClass().getName());
                    continue;
                }
                Map<?,?> newImage = (Map<?,?>) newImageObj;
                Object symbolObj = newImage.get("SymbolKey");
                String symbol = null;
                if (symbolObj instanceof Map) {
                    Object sVal = ((Map<?,?>)symbolObj).get("S");
                    if (sVal != null) symbol = sVal.toString();
                } else if (symbolObj != null) {
                    symbol = symbolObj.toString();
                }
                Object tradedObj = newImage.get("TradedDate");
                String tradedDate = null;
                if (tradedObj instanceof Map) {
                    Object tVal = ((Map<?,?>)tradedObj).get("S");
                    if (tVal != null) tradedDate = tVal.toString();
                } else if (tradedObj != null) {
                    tradedDate = tradedObj.toString();
                }
                try {
                    QueryResponse qr = querySymbolAscending(symbol);
                    List<Map<String, AttributeValue>> items = qr.items();
                    List<Double> closes = items.stream().map(it -> safeGetDouble(it, "Close")).collect(Collectors.toList());
                    List<Double> highs = items.stream().map(it -> safeGetDouble(it, "High")).collect(Collectors.toList());
                    List<Double> lows = items.stream().map(it -> safeGetDouble(it, "Low")).collect(Collectors.toList());
                    Double ma20 = ma(closes,20); Double ma50 = ma(closes,50); Double ma200 = ma(closes,200);
                    Double rsi14 = rsi(closes,14);
                    double[] macdTrip = macd(closes);
                    Double atrVal = atr(highs,lows,closes,14);
                    Map<String,String> sigMap = computeSignal(macdTrip[0], macdTrip[1], rsi14);
                    String signal = sigMap.get("signal"); String confidence = sigMap.get("confidence");
                    List<String> updateParts = new ArrayList<>();
                    Map<String, AttributeValue> vals = new HashMap<>();
                    if (ma20 != null && !hasKey(newImage, "MA20")) { updateParts.add("MA20 = if_not_exists(MA20, :ma20)"); vals.put(":ma20", AttributeValue.builder().n(format(ma20)).build()); }
                    if (ma50 != null && !hasKey(newImage, "MA50")) { updateParts.add("MA50 = if_not_exists(MA50, :ma50)"); vals.put(":ma50", AttributeValue.builder().n(format(ma50)).build()); }
                    if (ma200 != null && !hasKey(newImage, "MA200")) { updateParts.add("MA200 = if_not_exists(MA200, :ma200)"); vals.put(":ma200", AttributeValue.builder().n(format(ma200)).build()); }
                    if (rsi14 != null && !hasKey(newImage, "RSI14")) { updateParts.add("RSI14 = if_not_exists(RSI14, :rsi14)"); vals.put(":rsi14", AttributeValue.builder().n(format(rsi14)).build()); }
                    if (!Double.isNaN(macdTrip[0]) && !hasKey(newImage, "MACD")) { updateParts.add("MACD = if_not_exists(MACD, :macd)"); vals.put(":macd", AttributeValue.builder().n(format(macdTrip[0])).build()); }
                    if (!Double.isNaN(macdTrip[1]) && !hasKey(newImage, "MACDSignal")) { updateParts.add("MACDSignal = if_not_exists(MACDSignal, :macd_sig)"); vals.put(":macd_sig", AttributeValue.builder().n(format(macdTrip[1])).build()); }
                    if (!Double.isNaN(macdTrip[2]) && !hasKey(newImage, "MACDHist")) { updateParts.add("MACDHist = if_not_exists(MACDHist, :macd_hist)"); vals.put(":macd_hist", AttributeValue.builder().n(format(macdTrip[2])).build()); }
                    if (atrVal != null && !hasKey(newImage, "ATR")) { updateParts.add("ATR = if_not_exists(ATR, :atr)"); vals.put(":atr", AttributeValue.builder().n(format(atrVal)).build()); }
                    if (!hasKey(newImage, "Signal")) { updateParts.add("Signal = if_not_exists(Signal, :signal)"); vals.put(":signal", AttributeValue.builder().s(signal).build()); }
                    if (!hasKey(newImage, "Confidence")) { updateParts.add("Confidence = if_not_exists(Confidence, :conf)"); vals.put(":conf", AttributeValue.builder().s(confidence).build()); }
                    if (!updateParts.isEmpty()) {
                        String updateExpr = "SET " + String.join(", ", updateParts);
                        Map<String, AttributeValue> key = Map.of("SymbolKey", AttributeValue.builder().s(symbol).build(), "TradedDate", AttributeValue.builder().s(tradedDate).build());
                        UpdateItemRequest uir = UpdateItemRequest.builder().tableName(tableName).key(key).updateExpression(updateExpr).expressionAttributeValues(vals).build();
                        dynamo.updateItem(uir);
                        logger.info("Updated indicators for {} {}", symbol, tradedDate);
                        String report = String.format("Analysis report for %s %s: Signal=%s, Confidence=%s, MA20=%s, MA50=%s, RSI14=%s", symbol, tradedDate, signal, confidence, ma20, ma50, rsi14);
                        notifyTelegram(report);
                        notifyEmail("Analysis report: " + symbol + " " + tradedDate, report);
                    } else {
                        logger.info("No computed values to write for {} {}", symbol, tradedDate);
                    }
                } catch (Exception e) {
                    logger.error("Error processing record: {}", e.getMessage());
                }
            }
            resp.put("status", "done");
            return resp;
        }

        resp.put("status", "no_action");
        return resp;
    }

    private boolean hasKey(Map<?,?> image, String k) { return image.containsKey(k); }

    private QueryResponse querySymbolAscending(String symbol) {
        Map<String, AttributeValue> exprVals = Map.of(":s", AttributeValue.builder().s(symbol).build());
        QueryRequest qr = QueryRequest.builder().tableName(tableName).keyConditionExpression("SymbolKey = :s").expressionAttributeValues(exprVals).scanIndexForward(true).build();
        return dynamo.query(qr);
    }

    private List<String> extractSymbols(Map<String,Object> event) {
        Object s = event.get("symbols");
        if (s instanceof List) {
            return ((List<?>)s).stream().map(Object::toString).collect(Collectors.toList());
        } else if (s instanceof String) {
            String str = (String) s;
            if (str.contains(",")) {
                return Arrays.stream(str.split(",")).map(String::trim).filter(x -> !x.isEmpty()).collect(Collectors.toList());
            } else if (!str.isEmpty()) {
                return Collections.singletonList(str.trim());
            }
        }
        return Collections.emptyList();
    }

    private List<String> discoverAllSymbols() {
        return Collections.emptyList();
    }

    private int backfillSymbolAlwaysOverride(String symbol, int backfillDays) {
        QueryResponse qr = querySymbolAscending(symbol);
        List<Map<String, AttributeValue>> items = qr.items();
        int updates = 0;
        List<Double> closes = items.stream().map(it -> safeGetDouble(it, "Close")).collect(Collectors.toList());
        List<Double> highs = items.stream().map(it -> safeGetDouble(it, "High")).collect(Collectors.toList());
        List<Double> lows = items.stream().map(it -> safeGetDouble(it, "Low")).collect(Collectors.toList());
        String threshold = java.time.LocalDate.now().minusDays(backfillDays - 1).toString();
        for (int idx = 0; idx < items.size(); idx++) {
            Map<String, AttributeValue> item = items.get(idx);
            String traded = item.containsKey("TradedDate") ? item.get("TradedDate").s() : null;
            if (traded == null || traded.compareTo(threshold) < 0) continue;
            List<Double> subCloses = closes.subList(0, Math.min(closes.size(), idx+1));
            List<Double> subHighs = highs.subList(0, Math.min(highs.size(), idx+1));
            List<Double> subLows = lows.subList(0, Math.min(lows.size(), idx+1));
            Double ma20 = ma(subCloses,20); Double ma50 = ma(subCloses,50); Double ma200 = ma(subCloses,200);
            Double rsi14 = rsi(subCloses,14);
            double[] macdTrip = macd(subCloses);
            Double atrVal = atr(subHighs, subLows, subCloses, 14);
            Map<String,String> sigMap = computeSignal(macdTrip[0], macdTrip[1], rsi14);
            String signal = sigMap.get("signal"); String confidence = sigMap.get("confidence");

            List<String> updateParts = new ArrayList<>();
            Map<String, AttributeValue> vals = new HashMap<>();
            if (ma20 != null) { updateParts.add("MA20 = :ma20"); vals.put(":ma20", AttributeValue.builder().n(format(ma20)).build()); }
            if (ma50 != null) { updateParts.add("MA50 = :ma50"); vals.put(":ma50", AttributeValue.builder().n(format(ma50)).build()); }
            if (ma200 != null) { updateParts.add("MA200 = :ma200"); vals.put(":ma200", AttributeValue.builder().n(format(ma200)).build()); }
            if (rsi14 != null) { updateParts.add("RSI14 = :rsi14"); vals.put(":rsi14", AttributeValue.builder().n(format(rsi14)).build()); }
            if (!Double.isNaN(macdTrip[0])) { updateParts.add("MACD = :macd"); vals.put(":macd", AttributeValue.builder().n(format(macdTrip[0])).build()); }
            if (!Double.isNaN(macdTrip[1])) { updateParts.add("MACDSignal = :macd_sig"); vals.put(":macd_sig", AttributeValue.builder().n(format(macdTrip[1])).build()); }
            if (!Double.isNaN(macdTrip[2])) { updateParts.add("MACDHist = :macd_hist"); vals.put(":macd_hist", AttributeValue.builder().n(format(macdTrip[2])).build()); }
            if (atrVal != null) { updateParts.add("ATR = :atr"); vals.put(":atr", AttributeValue.builder().n(format(atrVal)).build()); }
            updateParts.add("Signal = :signal"); updateParts.add("Confidence = :conf"); vals.put(":signal", AttributeValue.builder().s(signal).build()); vals.put(":conf", AttributeValue.builder().s(confidence).build());

            if (updateParts.isEmpty()) continue;
            String updateExpr = "SET " + String.join(", ", updateParts);
            Map<String, AttributeValue> key = Map.of(
                "SymbolKey", AttributeValue.builder().s(item.get("SymbolKey").s()).build(),
                "TradedDate", AttributeValue.builder().s(item.get("TradedDate").s()).build()
            );
            UpdateItemRequest uir = UpdateItemRequest.builder().tableName(tableName).key(key).updateExpression(updateExpr).expressionAttributeValues(vals).build();
            try { dynamo.updateItem(uir); updates++; } catch (Exception e) { logger.error("Backfill UpdateItem failed for {}: {}", key, e.getMessage()); }
        }
        return updates;
    }

    private Map<String,String> computeSignal(Double macdLine, Double macdSignal, Double rsiVal) {
        String signal = "HOLD";
        String confidence = "LOW";
        if (macdLine == null || macdSignal == null || rsiVal == null || Double.isNaN(macdLine) || Double.isNaN(macdSignal) || Double.isNaN(rsiVal)) return Map.of("signal", signal, "confidence", confidence);
        if (macdLine > macdSignal && rsiVal < 70) { signal = "BUY"; confidence = rsiVal < 60 ? "HIGH" : "MEDIUM"; }
        else if (macdLine < macdSignal && rsiVal > 70) { signal = "SELL"; confidence = rsiVal > 80 ? "HIGH" : "MEDIUM"; }
        return Map.of("signal", signal, "confidence", confidence);
    }

    private Double ma(List<Double> series, int period) {
        if (series.size() < period) return null;
        double sum = 0.0; for (int i = series.size()-period; i < series.size(); i++) sum += series.get(i);
        return sum/period;
    }

    private Double ema(List<Double> series, int period) {
        if (series.size() < period) return null;
        double k = 2.0/(period+1);
        double emaPrev = 0.0; for (int i = 0; i < period; i++) emaPrev += series.get(i); emaPrev /= period;
        for (int i = period; i < series.size(); i++) { emaPrev = (series.get(i)-emaPrev)*k + emaPrev; }
        return emaPrev;
    }

    private double[] macd(List<Double> series) {
        Double e12 = ema(series, 12); Double e26 = ema(series, 26);
        if (e12 == null || e26 == null) return new double[]{Double.NaN, Double.NaN, Double.NaN};
        double macdLine = e12 - e26;
        List<Double> macdSeries = new ArrayList<>();
        for (int i = 0; i < series.size(); i++) {
            List<Double> sub = series.subList(0, i+1);
            Double a12 = ema(sub, 12); Double a26 = ema(sub, 26);
            if (a12 == null || a26 == null) macdSeries.add(null); else macdSeries.add(a12 - a26);
        }
        List<Double> clean = macdSeries.stream().filter(Objects::nonNull).collect(Collectors.toList());
        Double signal = clean.size() >= 9 ? ema(clean, 9) : null;
        Double hist = (signal != null) ? macdLine - signal : null;
        return new double[]{macdLine, signal==null?Double.NaN:signal, hist==null?Double.NaN:hist};
    }

    private Double rsi(List<Double> series, int period) {
        if (series.size() < period+1) return null;
        double gains=0.0, losses=0.0;
        for (int i = series.size()-period; i < series.size(); i++) { double d = series.get(i)-series.get(i-1); if (d>0) gains+=d; else losses-=d; }
        if (gains+losses==0) return 50.0;
        double rs = (gains/period) / (losses==0?1e-9:(losses/period));
        if (Double.isInfinite(rs)) return 100.0; return 100 - (100/(1+rs));
    }

    private Double atr(List<Double> highs, List<Double> lows, List<Double> closes, int period) {
        if (highs.size() < period+1 || lows.size() < period+1 || closes.size() < period+1) return null;
        List<Double> trs = new ArrayList<>();
        for (int i = 1; i < closes.size(); i++) {
            double tr = Math.max(highs.get(i)-lows.get(i), Math.max(Math.abs(highs.get(i)-closes.get(i-1)), Math.abs(lows.get(i)-closes.get(i-1))));
            trs.add(tr);
        }
        if (trs.size() < period) return null;
        double sum = 0.0; for (int i = trs.size()-period; i < trs.size(); i++) sum += trs.get(i);
        return sum/period;
    }

    private double safeGetDouble(Map<String, AttributeValue> item, String key) {
        try { if (!item.containsKey(key)) return 0.0; AttributeValue v = item.get(key); if (v.n()!=null) return Double.parseDouble(v.n()); if (v.s()!=null) return Double.parseDouble(v.s()); } catch (Exception ignored) {}
        return 0.0;
    }

    private String format(Double d) { return String.format(Locale.US, "%.2f", d); }

    private boolean notifyTelegram(String message) {
        try {
            String token = System.getenv("TELEGRAM_BOT_TOKEN");
            String chatId = System.getenv("TELEGRAM_CHAT_ID");
            if (token==null || chatId==null) { logger.warn("Telegram env not set"); return false; }
            String url = String.format("https://api.telegram.org/bot%s/sendMessage", token);
            URL u = new URL(url);
            HttpURLConnection con = (HttpURLConnection) u.openConnection();
            con.setRequestMethod("POST"); con.setDoOutput(true);
            String payload = "chat_id="+chatId+"&text="+java.net.URLEncoder.encode(message, StandardCharsets.UTF_8);
            byte[] out = payload.getBytes(StandardCharsets.UTF_8);
            con.setFixedLengthStreamingMode(out.length);
            con.setRequestProperty("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8");
            con.connect(); try (OutputStream os = con.getOutputStream()) { os.write(out); }
            int code = con.getResponseCode(); return code==200;
        } catch (Exception e) { logger.error("Telegram notify failed: {}", e.getMessage()); return false; }
    }

    private boolean notifyEmail(String subject, String body) {
        try {
            String from = System.getenv("SES_FROM");
            String toRaw = System.getenv("SES_TO");
            if (from==null || toRaw==null) { logger.warn("SES env not set"); return false; }
            List<String> toList = Arrays.stream(toRaw.split(","))
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .collect(Collectors.toList());
            SendEmailRequest req = SendEmailRequest.builder()
                .destination(Destination.builder().toAddresses(toList).build())
                .message(Message.builder().subject(Content.builder().data(subject).build()).body(Body.builder().text(Content.builder().data(body).build()).build()).build())
                .source(from).build();
            sesClient.sendEmail(req); return true;
        } catch (Exception e) { logger.error("SES notify failed: {}", e.getMessage()); return false; }
    }
}
