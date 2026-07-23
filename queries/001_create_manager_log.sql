CREATE TABLE IF NOT EXISTS manager_log (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
