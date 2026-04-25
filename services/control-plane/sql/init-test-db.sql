-- Initialize a sibling database for the integration test suite.
-- The dev database is `almighty`; tests use `almighty_test` so they can
-- truncate freely without disturbing dev data.
CREATE DATABASE almighty_test;
