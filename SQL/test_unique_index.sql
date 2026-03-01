-- 测试: UNIQUE INDEX
CREATE TABLE test_unique (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100),
    email VARCHAR(255),
    INDEX idx_name (name)
);
