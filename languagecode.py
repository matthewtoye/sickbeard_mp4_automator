from babelfish import Language


def getAlpha3TCode(code):  # We need to make sure that language codes are alpha3T
    """
        :param    code: Alpha2, Alpha3, or Alpha3b code.
        :type     code: C{str}

        :return: Alpha3t language code (ISO 639-2/T) as C{str}
    """
    lang = 'und'
    code = code.strip().lower()

    if len(code) == 3:
        try:
            lang = Language(code).alpha3t
        except:
            try:
                lang = Language.fromalpha3b(code).alpha3t
            except:
                try:
                    lang = Language.fromalpha3t(code).alpha3t
                except:
                    pass

    elif len(code) == 2:
        lang = Language.fromalpha2(code).alpha3t

    return lang


def validateLangCode(code):
    """
    :param code: alpha2, alpha3 or alpha3b code or list of codes
    :type code: list or string
    :return:  list or string containing valid alpha3 codes
    """
    lang = 'und'
    if code:
        if isinstance(code, list):
            lang = filter(lambda x: x != 'und', list(set(map(getAlpha3TCode, code))))
            lang = 'und' if lang == [] else lang

        elif isinstance(code, basestring):
            lang = getAlpha3TCode(code)

    return lang
