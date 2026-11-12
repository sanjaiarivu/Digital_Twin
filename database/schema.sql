-- MySQL 8 schema. Flask-SQLAlchemy creates equivalent tables on startup.
CREATE DATABASE IF NOT EXISTS digital_twin CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE digital_twin;
CREATE TABLE IF NOT EXISTS machine (
  id VARCHAR(40) PRIMARY KEY, name VARCHAR(100) NOT NULL, type VARCHAR(80) NOT NULL,
  location VARCHAR(100) NOT NULL, expected_rpm DOUBLE NOT NULL, created_at DATETIME
);
CREATE TABLE IF NOT EXISTS reading (
  id INT AUTO_INCREMENT PRIMARY KEY, machine_id VARCHAR(40) NOT NULL, temperature DOUBLE NOT NULL,
  vibration DOUBLE NOT NULL, rpm DOUBLE NOT NULL, health DOUBLE NOT NULL, failure_risk DOUBLE NOT NULL,
  source VARCHAR(20) NOT NULL, created_at DATETIME, INDEX ix_reading_machine_id (machine_id),
  INDEX ix_reading_created_at (created_at), FOREIGN KEY (machine_id) REFERENCES machine(id)
);
CREATE TABLE IF NOT EXISTS alert (
  id INT AUTO_INCREMENT PRIMARY KEY, machine_id VARCHAR(40) NOT NULL, type VARCHAR(100) NOT NULL,
  reading VARCHAR(80) NOT NULL, severity VARCHAR(20) NOT NULL, status VARCHAR(20) NOT NULL,
  created_at DATETIME, INDEX ix_alert_machine_id (machine_id)
);
CREATE TABLE IF NOT EXISTS prediction (
  id INT AUTO_INCREMENT PRIMARY KEY, machine_id VARCHAR(40) NOT NULL, failure_risk DOUBLE NOT NULL,
  health DOUBLE NOT NULL, method VARCHAR(60) NOT NULL, created_at DATETIME
);
CREATE TABLE IF NOT EXISTS maintenance (
  id INT AUTO_INCREMENT PRIMARY KEY, machine_id VARCHAR(40) NOT NULL, description VARCHAR(500) NOT NULL,
  performed_by VARCHAR(100), created_at DATETIME
);
