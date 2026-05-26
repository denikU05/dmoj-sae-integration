;; Cyclomatic complexity decision nodes
[
  (if_statement)
  (elif_clause)
  (for_statement)
  (while_statement)
  (except_clause)
  (conditional_expression)
  (boolean_operator)
  (if_clause)
  (case_clause)
] @decision

;; Branch operations mapping
[
  (if_statement)
  (elif_clause)
  (else_clause)
  (except_clause)
  (case_clause)
] @branch

;; Loop structures tracking
[
  (for_statement)
  (while_statement)
  (for_in_clause)
] @loop