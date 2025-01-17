# -*- coding: utf-8 -*-
import os
import logging
import tempfile
try:
    import cmuclmtk
except ImportError:
    pass
from .g2p import PhonetisaurusG2P
from naomi import profile


def delete_temp_file(file_to_delete):
    if True:
        os.remove(file_to_delete)


def get_languagemodel_path(path):
    """
    Returns:
        The path of the the pocketsphinx languagemodel file as string
    """
    return os.path.join(path, 'languagemodel')


def get_dictionary_path(path):
    """
    Returns:
        The path of the pocketsphinx dictionary file as string
    """
    return os.path.join(path, 'dictionary')


def get_thresholds_path(path):
    """
    Returns:
        The path to the pocketsphinx_kws keywords file as string
    """
    return os.path.join(path, 'kws.thresholds')


def compile_vocabulary(directory, phrases):
    """
    Compiles the vocabulary to the Pocketsphinx format by creating a
    languagemodel and a dictionary.

    Arguments:
        phrases -- a list of phrases that this vocabulary will contain
    """
    print("phrases: {}".format(phrases))
    logger = logging.getLogger(__name__)
    languagemodel_path = get_languagemodel_path(directory)
    dictionary_path = get_dictionary_path(directory)

    executable = profile.get(
        ['pocketsphinx', 'phonetisaurus_executable'],
        'phonetisaurus-g2p'
    )
    nbest = profile.get(
        ['pocketsphinx', 'nbest'],
        3
    )
    fst_model = profile.get(['pocketsphinx', 'fst_model'])
    fst_model_alphabet = profile.get(
        ['pocketsphinx', 'fst_model_alphabet'],
        'arpabet'
    )

    if not fst_model:
        raise ValueError('FST model not specified!')

    if not os.path.exists(fst_model):
        raise OSError('FST model {} does not exist!'.format(fst_model))

    g2pconverter = PhonetisaurusG2P(
        executable,
        fst_model,
        fst_model_alphabet=fst_model_alphabet,
        nbest=nbest
    )

    logger.debug('Languagemodel path: %s' % languagemodel_path)
    logger.debug('Dictionary path:    %s' % dictionary_path)
    text = " ".join(
        [("<s> %s </s>" % phrase.upper()) for phrase in phrases]
    )
    # There's some strange issue when text2idngram sometime can't find any
    # input (although it's there). For a reason beyond me, this can be fixed
    # by appending a space char to the string.
    text += ' '
    logger.debug('Compiling languagemodel...')
    vocabulary = compile_languagemodel(text, languagemodel_path)
    logger.debug('Starting dictionary...')
    compile_dictionary(g2pconverter, vocabulary, dictionary_path)


def compile_languagemodel(text, output_file):
    """
    Compiles the languagemodel from a text.

    Arguments:
        text -- the text the languagemodel will be generated from
        output_file -- the path of the file this languagemodel will
                       be written to

    Returns:
        A list of all unique words this vocabulary contains.
    """
    if len(text.strip()) == 0:
        raise ValueError('No text to compile into languagemodel!')

    logger = logging.getLogger(__name__)

    with tempfile.NamedTemporaryFile(suffix='.vocab', delete=False) as f:
        vocab_file = f.name

    # Create vocab file from text
    logger.debug("Creating vocab file: '%s'" % vocab_file)
    cmuclmtk.text2vocab(text, vocab_file)

    # Get words from vocab file
    logger.debug("Getting words from vocab file and removing it afterwards...")
    words = []
    with open(vocab_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line.startswith('#') and line not in ('<s>', '</s>'):
                words.append(line)

    if len(words) == 0:
        logger.warning('Vocab file seems to be empty!')

    # Create language model from text
    logger.debug("Creating languagemodel file: '%s'" % output_file)
    cmuclmtk.text2lm(text, output_file, vocab_file=vocab_file)

    # Remote the vocab file
    delete_temp_file(vocab_file)

    return words


def compile_dictionary(g2pconverter, words, output_file):
    """
    Compiles the dictionary from a list of words.

    Arguments:
        words -- a list of all unique words this vocabulary contains
        output_file -- the path of the file this dictionary will
                       be written to
    """
    # create the dictionary
    logger = logging.getLogger(__name__)
    logger.debug("Getting phonemes for %d words..." % len(words))
    try:
        phonemes = g2pconverter.translate([word.upper() for word in words])
        logger.debug(phonemes)
    except ValueError as e:
        print(str(e))
        if str(e) == 'Input symbol not found':
            logger.debug("Upper failed trying lower()")
            phonemes = g2pconverter.translate([word.lower() for word in words])
        else:
            raise e

    logger.debug("Creating dict file: '%s'" % output_file)
    with open(output_file, "w") as f:
        for word, pronounciations in phonemes.items():
            for i, pronounciation in enumerate(pronounciations, start=1):
                if i == 1:
                    line = "%s\t%s\n" % (
                        word.upper(),
                        pronounciation
                    )
                else:
                    line = "%s(%d)\t%s\n" % (
                        word.upper(),
                        i,
                        pronounciation
                    )
                f.write(line)
