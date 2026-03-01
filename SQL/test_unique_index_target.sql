-- 测试: UNIQUE INDEX (添加唯一索引)
CREATE TABLE test_unique (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(100) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(20),
    UNIQUE INDEX idx_username (username),
    UNIQUE INDEX idx_phone (phone),
    INDEX idx_email (email)
);
