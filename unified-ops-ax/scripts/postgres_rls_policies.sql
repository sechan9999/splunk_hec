-- ====================================================================
-- PostgreSQL Row-Level Security (RLS) Policy Migration Script
-- Unified Ops AX Enterprise Security Trimming & Data Isolation
-- ====================================================================

-- 1. Enable RLS on core entity tables
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE as_tickets ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- Force RLS even for table owner / admin users
ALTER TABLE customers FORCE ROW LEVEL SECURITY;
ALTER TABLE as_tickets FORCE ROW LEVEL SECURITY;
ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY;

-- 2. Create customer isolation policies
-- Managers and Accounting can access all customers; Sales reps access owned customers only.
CREATE POLICY customer_sales_isolation_policy ON customers
    FOR ALL
    USING (
        current_setting('app.current_user_role', true) IN ('manager', 'accounting')
        OR (
            current_setting('app.current_user_role', true) = 'sales'
            AND owner_employee_id = current_setting('app.current_user_id', true)
        )
    );

-- 3. Create AS ticket isolation policies
-- Managers can access all tickets; AS reps access assigned or unassigned tickets.
CREATE POLICY as_ticket_isolation_policy ON as_tickets
    FOR ALL
    USING (
        current_setting('app.current_user_role', true) = 'manager'
        OR (
            current_setting('app.current_user_role', true) = 'as'
            AND (assigned_employee_id IS NULL OR assigned_employee_id = current_setting('app.current_user_id', true))
        )
    );

-- 4. Create audit log security trimming policies
-- Manager role only for audit logs inspection.
CREATE POLICY audit_log_manager_policy ON audit_logs
    FOR SELECT
    USING (
        current_setting('app.current_user_role', true) = 'manager'
    );
