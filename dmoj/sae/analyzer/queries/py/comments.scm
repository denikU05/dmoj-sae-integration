;; Match inline or block comments
(comment) @comment

;; Match independent string literals acting as Docstrings or statement comments
(expression_statement (string) @comment)

(expression_statement (concatenated_string)) @comment