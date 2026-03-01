-- 测试: ADD COLUMN (新增多列)
CREATE TABLE test_add (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100),
    email VARCHAR(255),
    phone VARCHAR(20),
    age INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
