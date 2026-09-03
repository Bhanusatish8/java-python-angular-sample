package com.example.controller;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api")
public class EmbeddingController {
    private final JdbcTemplate jdbc;
    private final WebClient webClient;
    private final String openaiKey;
    private final int dim = 1536;

    public EmbeddingController(JdbcTemplate jdbc, @Value("${OPENAI_API_KEY:}") String openaiKey) {
        this.jdbc = jdbc;
        this.webClient = WebClient.create();
        this.openaiKey = openaiKey;
    }

    @PostMapping("/embeddings")
    public ResponseEntity<?> createEmbedding(@RequestBody Map<String, String> body) {
        String content = body.get("content");
        if (!StringUtils.hasText(content)) {
            return ResponseEntity.badRequest().body(Map.of("error", "content is required"));
        }

        // If OPENAI_API_KEY provided, attempt to call embeddings API, otherwise store content only
        if (StringUtils.hasText(openaiKey)) {
            try {
                Map resp = webClient.post()
                        .uri("https://api.openai.com/v1/embeddings")
                        .header("Authorization", "Bearer " + openaiKey)
                        .bodyValue(Map.of("model", "text-embedding-3-large", "input", content))
                        .retrieve()
                        .bodyToMono(Map.class)
                        .block();

                if (resp != null && resp.containsKey("data")) {
                    Object data = resp.get("data");
                    if (data instanceof List) {
                        Object first = ((List)data).get(0);
                        if (first instanceof Map && ((Map)first).get("embedding") instanceof List) {
                            List<Double> emb = (List<Double>) ((Map)first).get("embedding");
                            String vecText = emb.toString(); // e.g. [0.1, 0.2,...]
                            // store using ::vector cast
                            jdbc.update("INSERT INTO documents (content, embedding) VALUES (?, ?::vector)", content, vecText);
                            return ResponseEntity.ok(Map.of("status", "stored", "dim", emb.size()));
                        }
                    }
                }
            } catch (Exception e) {
                // fallthrough: store content only
                jdbc.update("INSERT INTO documents (content) VALUES (?)", content);
                return ResponseEntity.ok(Map.of("status", "stored_without_embedding", "error", e.getMessage()));
            }
        } else {
            jdbc.update("INSERT INTO documents (content) VALUES (?)", content);
            return ResponseEntity.ok(Map.of("status", "stored_without_embedding"));
        }

        return ResponseEntity.status(500).body(Map.of("error", "failed to create embedding"));
    }
}
