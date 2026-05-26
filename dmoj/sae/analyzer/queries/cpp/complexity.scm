;; Cyclomatic complexity decision points mapping
[
  (if_statement)
  (for_statement)
  (for_range_loop)
  (while_statement)
  (do_statement)
  (case_statement)
  (catch_clause)
  (conditional_expression)
  (preproc_if)
  (preproc_ifdef)
  (preproc_elif)
  (binary_expression operator: ["&&" "||"])
] @decision

;; Branches tracking
[
  (if_statement)
  (case_statement)
  (catch_clause)
] @branch

;; Loop control blocks
[
  (for_statement)
  (for_range_loop)
  (while_statement)
  (do_statement)
] @loop