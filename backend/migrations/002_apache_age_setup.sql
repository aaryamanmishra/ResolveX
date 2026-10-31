-- ResolveX AI — Migration 002: Apache AGE Graph Extension Setup
-- PRD §8.3 & §12.1: Apache AGE open-source graph extension in PostgreSQL.
-- Notes: If running on standard PostgreSQL without the AGE extension compiled,
-- this script is skipped or executed in an AGE-enabled container.

CREATE EXTENSION IF NOT EXISTS age;
LOAD 'age';
SET search_path = ag_catalog, "$user", public;

-- Initialize graph for ResolveX fraud relationships
SELECT create_graph('resolvex_fraud_graph');

-- Vertex Labels:
-- CustomerToken, Payment, Merchant, DeviceToken, PaymentInstrumentToken,
-- UPIReferenceToken, IPAddressToken, Refund, Case, ProviderEvent
SELECT create_vlabel('resolvex_fraud_graph', 'CustomerToken');
SELECT create_vlabel('resolvex_fraud_graph', 'Payment');
SELECT create_vlabel('resolvex_fraud_graph', 'Merchant');
SELECT create_vlabel('resolvex_fraud_graph', 'DeviceToken');
SELECT create_vlabel('resolvex_fraud_graph', 'PaymentInstrumentToken');
SELECT create_vlabel('resolvex_fraud_graph', 'UPIReferenceToken');
SELECT create_vlabel('resolvex_fraud_graph', 'IPAddressToken');
SELECT create_vlabel('resolvex_fraud_graph', 'Refund');
SELECT create_vlabel('resolvex_fraud_graph', 'Case');
SELECT create_vlabel('resolvex_fraud_graph', 'ProviderEvent');

-- Edge Labels:
-- INITIATED_BY, PAID_TO, USED_DEVICE, USED_INSTRUMENT, HAS_REFERENCE,
-- LINKED_REFUND, FLAGGED_IN_CASE, SAME_TOKEN_AS, PREVIOUSLY_REVIEWED_WITH
SELECT create_elabel('resolvex_fraud_graph', 'INITIATED_BY');
SELECT create_elabel('resolvex_fraud_graph', 'PAID_TO');
SELECT create_elabel('resolvex_fraud_graph', 'USED_DEVICE');
SELECT create_elabel('resolvex_fraud_graph', 'USED_INSTRUMENT');
SELECT create_elabel('resolvex_fraud_graph', 'HAS_REFERENCE');
SELECT create_elabel('resolvex_fraud_graph', 'LINKED_REFUND');
SELECT create_elabel('resolvex_fraud_graph', 'FLAGGED_IN_CASE');
SELECT create_elabel('resolvex_fraud_graph', 'SAME_TOKEN_AS');
SELECT create_elabel('resolvex_fraud_graph', 'PREVIOUSLY_REVIEWED_WITH');
