#!/bin/bash
# SchemaDiff - SQL Schema Diff Tool

# 设置颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 默认参数
SOURCE=""
TARGET=""
OUTPUT=""
DIALECT="mysql"

# 打印帮助
help() {
    echo "SchemaDiff - SQL Schema Diff & Migration Generator"
    echo ""
    echo "Usage: ./run.sh [OPTIONS] <source> <target>"
    echo ""
    echo "Options:"
    echo "  -h, --help           Show this help"
    echo "  -d, --dialect        SQL dialect (mysql/postgres) [default: mysql]"
    echo "  -o, --output FILE    Output migration script to FILE"
    echo ""
    echo "Examples:"
    echo "  ./run.sh SQL/users_v1.sql SQL/users_v2.sql"
    echo "  ./run.sh backup/v1 SQL -o migration.sql"
    echo "  ./run.sh -d postgres old.sql new.sql -o upgrade.sql"
}

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            help
            exit 0
            ;;
        -d|--dialect)
            DIALECT="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT="$2"
            shift 2
            ;;
        *)
            if [ -z "$SOURCE" ]; then
                SOURCE="$1"
            elif [ -z "$TARGET" ]; then
                TARGET="$1"
            fi
            shift
            ;;
    esac
done

# 检查参数
if [ -z "$SOURCE" ] || [ -z "$TARGET" ]; then
    echo -e "${YELLOW}Error: Source and Target are required${NC}"
    help
    exit 1
fi

# 构建命令
CMD="python3 main.py $SOURCE $TARGET --dialect $DIALECT"

if [ -n "$OUTPUT" ]; then
    CMD="$CMD -o $OUTPUT"
fi

# 执行
echo -e "${GREEN}Running SchemaDiff...${NC}"
echo "Command: $CMD"
echo ""

eval $CMD
