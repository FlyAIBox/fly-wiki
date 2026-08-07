-- 为 Langfuse 在同一 Postgres 实例上创建独立数据库，避免与 FlyWiki 领域数据混用。
-- 该脚本仅在数据卷首次初始化时执行一次。
SELECT 'CREATE DATABASE langfuse'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'langfuse')\gexec
