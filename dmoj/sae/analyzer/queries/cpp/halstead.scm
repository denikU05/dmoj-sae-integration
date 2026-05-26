;; Operators - symbols
(binary_expression operator: _ @operator)
(unary_expression operator: _ @operator)
(assignment_expression operator: _ @operator)
(update_expression operator: _ @operator)

;; Operators - keywords
[
  "?" ":"
  "if" "for" "while" "do" "return" "switch" "case" "default"
  "break" "continue" "else" "goto"
  "try" "catch" "throw"
  "new" "delete" 
  "sizeof"
] @operator

;; Operands
[
  (identifier)
  (type_identifier)
  (primitive_type)
  (number_literal)
  (string_literal)
  (char_literal)
  (true)
  (false)
  (null)
  (this)
] @operand