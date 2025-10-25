package com.tradebot.analysis;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;
import com.amazonaws.services.dynamodbv2.AmazonDynamoDB;
import com.amazonaws.services.dynamodbv2.AmazonDynamoDBClientBuilder;
import com.amazonaws.services.dynamodbv2.model.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.JsonNode;

import java.util.*;
import java.time.Instant;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;

public class AnalysisHandler implements RequestHandler<Map<String, Object>, Map<String, Object>> {
    
    private final AmazonDynamoDB dynamoDB;
    private final ObjectMapper objectMapper;
    private final String tableName;
    
    public AnalysisHandler() {
        this.dynamoDB = AmazonDynamoDBClientBuilder.defaultClient();
        this.objectMapper = new ObjectMapper();
        this.tableName = System.getenv().getOrDefault("DYNAMODB_TABLE", "tradebot_signals_table");
    }
    
    @Override
    public Map<String, Object> handleRequest(Map<String, Object> event, Context context) {
        Map<String, Object> response = new HashMap<>();
        
        try {
            System.out.println("Analysis Lambda triggered with event: " + objectMapper.writeValueAsString(event));
            
            // Extract parameters from event
            List<String> symbols = getSymbolsFromEvent(event);
            int backfillDays = getBackfillDays(event);
            
            System.out.println("Processing " + symbols.size() + " symbols for " + backfillDays + " days");
            
            List<String> processedSymbols = new ArrayList<>();
            List<String> errorDetails = new ArrayList<>();
            
            // Process each symbol
            for (String symbol : symbols) {
                try {
                    System.out.println("Analyzing symbol: " + symbol);
                    
                    // Fetch historical data
                    List<Map<String, AttributeValue>> historicalData = fetchHistoricalData(symbol, backfillDays);
                    
                    if (!historicalData.isEmpty()) {
                        // Perform analysis
                        List<Map<String, Object>> signals = performTechnicalAnalysis(symbol, historicalData);
                        
                        // Store signals
                        if (!signals.isEmpty()) {
                            storeSignals(symbol, signals);
                            processedSymbols.add(symbol);
                            System.out.println("Successfully analyzed " + symbol + " - Generated " + signals.size() + " signals");
                        } else {
                            System.out.println("No signals generated for " + symbol);
                        }
                    } else {
                        System.out.println("No historical data found for " + symbol);
                        errorDetails.add(symbol + ": No historical data");
                    }
                    
                } catch (Exception e) {
                    System.err.println("Error analyzing symbol " + symbol + ": " + e.getMessage());
                    errorDetails.add(symbol + ": " + e.getMessage());
                }
            }
            
            // Prepare response
            response.put("statusCode", 200);
            response.put("message", "Analysis completed");
            response.put("processedSymbols", processedSymbols);
            response.put("totalSymbols", symbols.size());
            response.put("errorDetails", errorDetails);
            
            System.out.println("Analysis completed. Processed: " + processedSymbols.size() + "/" + symbols.size());
            
        } catch (Exception e) {
            System.err.println("Critical error in analysis: " + e.getMessage());
            e.printStackTrace();
            
            response.put("statusCode", 500);
            response.put("message", "Analysis failed: " + e.getMessage());
        }
        
        return response;
    }
    
    @SuppressWarnings("unchecked")
    private List<String> getSymbolsFromEvent(Map<String, Object> event) {
        Object symbolsObj = event.get("symbols");
        if (symbolsObj instanceof List) {
            return (List<String>) symbolsObj;
        }
        // Default symbols
        return Arrays.asList("RELIANCE", "TCS", "ICICIBANK");
    }
    
    private int getBackfillDays(Map<String, Object> event) {
        Object backfillObj = event.get("backfilldays");
        if (backfillObj instanceof Number) {
            return ((Number) backfillObj).intValue();
        }
        return 3; // Default
    }
    
    private List<Map<String, AttributeValue>> fetchHistoricalData(String symbol, int days) {
        try {
            LocalDate endDate = LocalDate.now();
            LocalDate startDate = endDate.minusDays(days);
            
            // Create scan request with filter
            ScanRequest scanRequest = new ScanRequest()
                .withTableName(tableName)
                .withFilterExpression("SymbolKey = :symbol AND TradedDate BETWEEN :startDate AND :endDate")
                .withExpressionAttributeValues(Map.of(
                    ":symbol", new AttributeValue().withS(symbol),
                    ":startDate", new AttributeValue().withS(startDate.format(DateTimeFormatter.ISO_LOCAL_DATE)),
                    ":endDate", new AttributeValue().withS(endDate.format(DateTimeFormatter.ISO_LOCAL_DATE))
                ));
            
            ScanResult result = dynamoDB.scan(scanRequest);
            List<Map<String, AttributeValue>> items = result.getItems();
            
            // Sort by date
            items.sort((a, b) -> {
                String dateA = a.get("TradedDate").getS();
                String dateB = b.get("TradedDate").getS();
                return dateA.compareTo(dateB);
            });
            
            System.out.println("Found " + items.size() + " records for " + symbol);
            return items;
            
        } catch (Exception e) {
            System.err.println("Error fetching data for " + symbol + ": " + e.getMessage());
            return new ArrayList<>();
        }
    }
    
    private List<Map<String, Object>> performTechnicalAnalysis(String symbol, List<Map<String, AttributeValue>> historicalData) {
        List<Map<String, Object>> signals = new ArrayList<>();
        
        try {
            if (historicalData.size() < 5) {
                System.out.println("Insufficient data for analysis: " + symbol);
                return signals;
            }
            
            // Convert to price data
            List<Double> closes = new ArrayList<>();
            List<Double> volumes = new ArrayList<>();
            
            for (Map<String, AttributeValue> record : historicalData) {
                closes.add(Double.parseDouble(record.get("Close").getN()));
                volumes.add(Double.parseDouble(record.get("Volume").getN()));
            }
            
            // Simple Moving Average Analysis
            if (closes.size() >= 10) {
                double sma5 = closes.subList(closes.size() - 5, closes.size()).stream()
                    .mapToDouble(Double::doubleValue).average().orElse(0.0);
                double sma10 = closes.subList(closes.size() - 10, closes.size()).stream()
                    .mapToDouble(Double::doubleValue).average().orElse(0.0);
                double currentPrice = closes.get(closes.size() - 1);
                
                if (sma5 > sma10 && currentPrice > sma5) {
                    Map<String, Object> signal = new HashMap<>();
                    signal.put("symbol", symbol);
                    signal.put("signalType", "BUY");
                    signal.put("indicator", "SMA_CROSSOVER");
                    signal.put("strength", "MEDIUM");
                    signal.put("price", currentPrice);
                    signal.put("details", String.format("SMA5(%.2f) > SMA10(%.2f)", sma5, sma10));
                    signals.add(signal);
                }
            }
            
            // RSI Analysis
            if (closes.size() >= 15) {
                double rsi = calculateRSI(closes, 14);
                double currentPrice = closes.get(closes.size() - 1);
                
                if (rsi < 30) {
                    Map<String, Object> signal = new HashMap<>();
                    signal.put("symbol", symbol);
                    signal.put("signalType", "BUY");
                    signal.put("indicator", "RSI_OVERSOLD");
                    signal.put("strength", "HIGH");
                    signal.put("price", currentPrice);
                    signal.put("details", String.format("RSI(%.2f) < 30 - Oversold", rsi));
                    signals.add(signal);
                } else if (rsi > 70) {
                    Map<String, Object> signal = new HashMap<>();
                    signal.put("symbol", symbol);
                    signal.put("signalType", "SELL");
                    signal.put("indicator", "RSI_OVERBOUGHT");
                    signal.put("strength", "HIGH");
                    signal.put("price", currentPrice);
                    signal.put("details", String.format("RSI(%.2f) > 70 - Overbought", rsi));
                    signals.add(signal);
                }
            }
            
            System.out.println("Generated " + signals.size() + " signals for " + symbol);
            
        } catch (Exception e) {
            System.err.println("Error in technical analysis for " + symbol + ": " + e.getMessage());
        }
        
        return signals;
    }
    
    private double calculateRSI(List<Double> prices, int period) {
        if (prices.size() < period + 1) {
            return 50.0; // Neutral RSI
        }
        
        List<Double> gains = new ArrayList<>();
        List<Double> losses = new ArrayList<>();
        
        for (int i = 1; i < prices.size(); i++) {
            double change = prices.get(i) - prices.get(i - 1);
            if (change > 0) {
                gains.add(change);
                losses.add(0.0);
            } else {
                gains.add(0.0);
                losses.add(Math.abs(change));
            }
        }
        
        if (gains.size() < period) {
            return 50.0;
        }
        
        double avgGain = gains.subList(gains.size() - period, gains.size()).stream()
            .mapToDouble(Double::doubleValue).average().orElse(0.0);
        double avgLoss = losses.subList(losses.size() - period, losses.size()).stream()
            .mapToDouble(Double::doubleValue).average().orElse(0.0);
        
        if (avgLoss == 0) {
            return 100.0;
        }
        
        double rs = avgGain / avgLoss;
        return 100.0 - (100.0 / (1.0 + rs));
    }
    
    private void storeSignals(String symbol, List<Map<String, Object>> signals) {
        try {
            for (Map<String, Object> signal : signals) {
                Map<String, AttributeValue> item = new HashMap<>();
                
                // **FIX: Properly convert to AttributeValue**
                item.put("SymbolKey", new AttributeValue().withS(symbol));
                item.put("TradedDate", new AttributeValue().withS(LocalDate.now().format(DateTimeFormatter.ISO_LOCAL_DATE)));
                item.put("SignalType", new AttributeValue().withS((String) signal.get("signalType")));
                item.put("Indicator", new AttributeValue().withS((String) signal.get("indicator")));
                item.put("Strength", new AttributeValue().withS((String) signal.get("strength")));
                item.put("Price", new AttributeValue().withN(String.valueOf(signal.get("price"))));
                item.put("Details", new AttributeValue().withS((String) signal.get("details")));
                item.put("Timestamp", new AttributeValue().withS(Instant.now().toString()));
                item.put("data_type", new AttributeValue().withS("signal"));
                
                PutItemRequest putRequest = new PutItemRequest()
                    .withTableName(tableName)
                    .withItem(item);
                
                dynamoDB.putItem(putRequest);
            }
            
            System.out.println("Stored " + signals.size() + " signals for " + symbol);
            
        } catch (Exception e) {
            System.err.println("Error storing signals for " + symbol + ": " + e.getMessage());
            throw new RuntimeException("Failed to store signals", e);
        }
    }
}
