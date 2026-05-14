SELECT 
    TO_CHAR(created_at, 'YYYY-MM') AS mes_referencia,
    category,
    COUNT(id) AS qtd_transacoes,
    ROUND(SUM(amount_cents) / 100.0, 2) AS volume_total_reais
FROM 
    transactions
WHERE 
    status = 'completed'
    AND category IN ('subscription', 'one_time', 'refund', 'credit_adjustment')
    AND created_at >= '2026-04-24'::timestamp - INTERVAL '6 months'
    AND created_at <= '2026-04-24'::timestamp
GROUP BY 
    1, 2
ORDER BY 
    1 ASC, 
    2 ASC;