;; Operators - symbols
(binary_operator operator: _ @operator)
(unary_operator operator: _ @operator)
(augmented_assignment operator: _ @operator)

;; Operators - keywords
["=" "and" "or" "not" "==" "!=" "<" "<=" ">" ">=" "in" "is" "if" "for" "while" "return" "yield" "break" "continue"] @operator

;; Operands
[ 
  (identifier)
  (integer)
  (float)
  (string)
  (true)
  (false)
  (none) 
] @operand