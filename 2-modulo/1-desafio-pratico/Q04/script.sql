SELECT 
    TO_CHAR(created_at, 'YYYY-MM') AS mes,
    category AS categoria,
    COUNT(id) AS quantidade_transacoes,
    (SUM(amount_cents) / 100.0)::NUMERIC(18, 2) AS volume_total_reais
FROM 
    transactions
WHERE 
    status = 'completed'
    AND created_at >= '2026-04-24'::DATE - INTERVAL '6 months'
    AND created_at <= '2026-04-24'::TIMESTAMP
GROUP BY 
    1, 2
ORDER BY 
    mes ASC, 
    categoria ASC;