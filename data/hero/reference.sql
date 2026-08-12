WITH recent_rows AS (
    SELECT
        q.mktcode,
        q.tgtcode,
        q.bizdate,
        q.volume,
        q.turnover,
        ROW_NUMBER() OVER (
            PARTITION BY q.mktcode, q.tgtcode
            ORDER BY q.bizdate DESC
        ) AS recent_no
    FROM newzl.hsj_stock_hq_basic AS q
),
cons_ordered AS (
    SELECT
        r.mktcode,
        r.tgtcode,
        r.bizdate,
        CASE WHEN r.volume > 0 AND r.mktcode IN (0, 1) THEN 1 ELSE 0 END AS matched,
        ROW_NUMBER() OVER (
            PARTITION BY r.mktcode, r.tgtcode
            ORDER BY r.bizdate
        ) AS all_no
    FROM recent_rows AS r
    WHERE r.recent_no <= 10
),
cons_matches AS (
    SELECT
        c.mktcode,
        c.tgtcode,
        c.all_no,
        ROW_NUMBER() OVER (
            PARTITION BY c.mktcode, c.tgtcode
            ORDER BY c.bizdate
        ) AS match_no
    FROM cons_ordered AS c
    WHERE c.matched = 1
),
cons_candidates AS (
    SELECT runs.mktcode, runs.tgtcode
    FROM (
        SELECT
            m.mktcode,
            m.tgtcode,
            m.all_no - m.match_no AS run_id,
            COUNT(*) AS run_length
        FROM cons_matches AS m
        GROUP BY m.mktcode, m.tgtcode, m.all_no - m.match_no
    ) AS runs
    GROUP BY runs.mktcode, runs.tgtcode
    HAVING MAX(runs.run_length) >= 3
),
exist_candidates AS (
    SELECT r.mktcode, r.tgtcode
    FROM recent_rows AS r
    WHERE
        r.recent_no <= 10
        AND r.turnover > 0
        AND r.mktcode = 1
        AND NOT (r.tgtcode >= '688000' AND r.tgtcode <= '688999')
    GROUP BY r.mktcode, r.tgtcode
    HAVING COUNT(*) >= 2
),
stage_candidates AS (
    SELECT c.mktcode, c.tgtcode
    FROM cons_candidates AS c
    INNER JOIN exist_candidates AS e
        ON c.mktcode = e.mktcode AND c.tgtcode = e.tgtcode
),
latest_date AS (
    SELECT MAX(q.bizdate) AS bizdate
    FROM newzl.hsj_stock_hq_basic AS q
),
ranked AS (
    SELECT
        q.mktcode,
        q.tgtcode,
        q.bizdate,
        ROW_NUMBER() OVER (
            ORDER BY q.turnover DESC, q.mktcode ASC, q.tgtcode ASC
        ) AS stable_rank
    FROM newzl.hsj_stock_hq_basic AS q
    INNER JOIN stage_candidates AS c
        ON q.mktcode = c.mktcode AND q.tgtcode = c.tgtcode
    INNER JOIN latest_date AS d ON q.bizdate = d.bizdate
    WHERE q.mktcode IN (0, 1)
)
SELECT r.mktcode, r.tgtcode, r.bizdate
FROM ranked AS r
WHERE r.stable_rank BETWEEN 1 AND 20
