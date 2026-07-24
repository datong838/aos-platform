-- Dev source DB seed for T4.6 MySQL connector (aos-dev-mysql)
-- 36 §7 · 钉死 utf8mb4，避免 Windows/容器默认 latin1 导致中文双重编码
SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;
SET character_set_client = utf8mb4;
SET character_set_connection = utf8mb4;
SET character_set_results = utf8mb4;

CREATE TABLE IF NOT EXISTS src_work_orders (
  id VARCHAR(64) PRIMARY KEY,
  title VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'open',
  site VARCHAR(64) NOT NULL DEFAULT 'DC-East',
  priority VARCHAR(8) NOT NULL DEFAULT 'P2'
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO src_work_orders (id, title, status, site, priority) VALUES
  ('mysql-wo-001', 'MySQL供数-巡检单', 'open', 'DC-East', 'P1'),
  ('mysql-wo-002', 'MySQL供数-备件', 'in_progress', 'DC-West', 'P0')
ON DUPLICATE KEY UPDATE title=VALUES(title);
