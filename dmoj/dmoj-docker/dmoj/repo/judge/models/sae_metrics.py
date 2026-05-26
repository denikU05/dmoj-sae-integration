METRIC_TRANSLATIONS = {
    'total_var_name_length': {
        'ru': 'Суммарная длина имен всех переменных',
        'en': 'Total variables\' names length'
    },
    'source_char_count': {
        'ru': 'Количество символов в исходном коде',
        'en': 'Source character count'
    },
    'sloc': {
        'ru': 'Количество значимых строк кода',
        'en': 'Source lines of code'
    },
    'unique_identifiers': {
        'ru': 'Количество уникальных идентификаторов',
        'en': 'Unique identifier count'
    },
    'comment_ratio': {
        'ru': 'Соотношение комментариев',
        'en': 'Comment ratio'
    },
    'keyword_goto_count': {
        'ru': 'Количество goto',
        'en': 'Goto count'
    },
    'max_line_length': {
        'ru': 'Максимальная длина строки',
        'en': 'Max line length'
    },
    'avg_identifier_length': {
        'ru': 'Средняя длина идентификатора',
        'en': 'Average identifier length'
    },
    'nesting_depth': {
        'ru': 'Максимальная глубина вложенности',
        'en': 'Max nesting depth'
    },
    'cyclomatic_complexity': {
        'ru': 'Цикломатическая сложность',
        'en': 'Cyclomatic complexity'
    },
    'branch_count': {
        'ru': 'Количество операторов ветвления',
        'en': 'Branch count'
    },
    'loop_count': {
        'ru': 'Количество циклов',
        'en': 'Loop count'
    },
    'modularity_ratio': {
        'ru': 'Индекс модульности',
        'en': 'Modularity ratio'
    },
    'magic_number_count': {
        'ru': 'Количество магических чисел',
        'en': 'Magic number count'
    },
    'halstead_volume': {
        'ru': 'Объём Холстеда',
        'en': 'Halstead volume'
    },
    'halstead_difficulty': {
        'ru': 'Сложность Холстеда',
        'en': 'Halstead difficulty'
    },
    'halstead_effort': {
        'ru': 'Трудоёмкость Холстеда',
        'en': 'Halstead effort'
    },
    'maintainability_index': {
        'ru': 'Индекс сопровождаемости',
        'en': 'Maintainability index'
    },
    'structural_duplication_ratio': {
        'ru': 'Индекс структурного дублирования',
        'en': 'Structural duplication ratio'
    },
}

# Generage default SAE config
DEFAULT_SAE_CONFIG = {
    key: {
        "enabled": False, 
        "direction": 'lower_better', 
        "weight": 1.0
    }
    for key, data in METRIC_TRANSLATIONS.items()
}

# Or create your own like like this
# DEFAULT_SAE_CONFIG = {
#    "total_var_name_length": {"enabled": False, "direction": "lower_better", "weight": 1.0},
#    # and so on...
#}