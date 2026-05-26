;; Operators - symbols
(binary_expression operator: _ @operator)
(unary_expression operator: _ @operator)
(assignment_expression operator: _ @operator)

;; Operators - keywords
["if" "for" "while" "do" "return" "switch" "case" "break" "continue" "else" "new" "instanceof" "++" "--"] @operator

;; Operands
(identifier) @operand
(decimal_integer_literal) @operand
(decimal_floating_point_literal) @operand