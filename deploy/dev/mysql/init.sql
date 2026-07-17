-- Dev source DB seed for T4.6 MySQL connector (aos-dev-mysql)
CREATE TABLE IF NOT EXISTS src_work_orders (
  id VARCHAR(64) PRIMARY KEY,
  title VARCHAR(255) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'open',
  site VARCHAR(64) NOT NULL DEFAULT 'DC-East',
  priority VARCHAR(8) NOT NULL DEFAULT 'P2'
);

INSERT INTO src_work_orders (id, title, status, site, priority) VALUES
  ('mysql-wo-001', 'MySQL供数-巡检单', 'open', 'DC-East', 'P1'),
  ('mysql-wo-002', 'MySQL供数-备件', 'in_progress', 'DC-West', 'P0')
ON DUPLICATE KEY UPDATE title=VALUES(title);
