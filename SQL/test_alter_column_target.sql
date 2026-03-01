-- 测试: ALTER COLUMN (修改列类型/长度/约束)
CREATE TABLE test_alter (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(100) NOT NULL,
    status TINYINT DEFAULT 1,
    total_amount DECIMAL(15,4) DEFAULT 0.00
);
