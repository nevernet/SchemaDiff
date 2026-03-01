-- 测试: FOREIGN KEY
CREATE TABLE test_fk_parent (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100)
);

CREATE TABLE test_fk_child (
    id INT PRIMARY KEY AUTO_INCREMENT,
    parent_id INT,
    title VARCHAR(100)
);
