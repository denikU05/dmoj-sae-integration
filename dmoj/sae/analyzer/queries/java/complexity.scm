;; Cyclomatic complexity decision points mapping
(if_statement) @decision
(for_statement) @decision
(enhanced_for_statement) @decision
(while_statement) @decision
(do_statement) @decision
(switch_expression) @decision
(ternary_expression) @decision
(catch_clause) @decision

;; Branches tracking
(if_statement alternative: (_) @branch)
(switch_block_statement_group) @branch
(catch_clause) @branch

;; Loop control blocks
(for_statement) @loop
(enhanced_for_statement) @loop
(while_statement) @loop
(do_statement) @loop