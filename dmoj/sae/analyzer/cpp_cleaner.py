import re

def extract_defines(code: str) -> dict:
    """
    Извлекает define макросы из C++ кода
    Возвращает словарь: имя макроса -> (аргументы, тело макроса)
    """
    defines = {}
    pattern = r'#define\s+(\w+)\s*(\([^\)]*\))?\s+(.*)'
    for match in re.findall(pattern, code):
        name, args, body = match
        args = args[1:-1].split(',') if args else []
        defines[name] = (args, body.strip())
    return defines

def expand_macros(code: str, defines: dict) -> str:
    """
    Раскрывает макросы в коде
    """
    lines = code.splitlines()
    expanded = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#define"):
            continue

        for name, (args, body) in defines.items():
            if args:
                # если у define есть параметры
                pattern = rf'\b{name}\s*\((.*?)\)'

                def replacer(match):
                    values = [v.strip() for v in match.group(1).split(',')]
                    result = body
                    for a, v in zip(args, values):
                        result = result.replace(a, v)
                    return result

                line = re.sub(pattern, replacer, line)
            else:
                line = re.sub(
                    rf'\b{name}\b',
                    lambda m: body,
                    line
                )

        expanded.append(line)

    return "\n".join(expanded)


def clean_cpp_code(code: str) -> str:
    """
    Очищает cpp код для дальнейшего анализа.
    Возвращает его как строку
    """
    defines = extract_defines(code)
    expanded_code = expand_macros(code, defines)

    return expanded_code