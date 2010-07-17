
lumiere_nfc = u"lumi\u00E8re"
Artonwall_nfc = u"\u00C4rtonwall.mp3"
Artonwall_nfd = u"A\u0308rtonwall.mp3"

TEST_FILENAMES = (
  Artonwall_nfc,
  u'test_file',
  u'Blah blah.txt',
)

# The following main helps to generate a test class for other operating
# systems.

if __name__ == "__main__":
    import sys
    import platform

    if len(sys.argv) != 2:
        print "Usage: %s lumi<e-grave>re" % sys.argv[0]
        sys.exit(1)
    
    print
    print "class MyWeirdOS(StringUtils, unittest.TestCase):"
    print "    uname = '%s'" % ' '.join(platform.uname())
    if sys.platform != "win32":
        print "    argv = %s" % repr(sys.argv[1])
    print "    platform = '%s'" % sys.platform
    print "    filesystem_encoding = '%s'" % sys.getfilesystemencoding()
    print "    output_encoding = '%s'" % sys.stdout.encoding
    print "    argv_encoding = '%s'" % (sys.platform == "win32" and 'ascii' or sys.stdout.encoding)
    print

    sys.exit(0)

from twisted.trial import unittest
from mock import patch
import sys, locale

from allmydata.test.common_util import ReallyEqualMixin
from allmydata.util.encodingutil import argv_to_unicode, unicode_to_url, \
    unicode_to_output, unicode_platform, get_output_encoding, _reload

from twisted.python import usage

class StringUtilsErrors(ReallyEqualMixin, unittest.TestCase):
    def tearDown(self):
        _reload()

    @patch('sys.stdout')
    def test_get_output_encoding(self, mock_stdout):
        mock_stdout.encoding = 'UTF-8'
        _reload()
        self.failUnlessReallyEqual(get_output_encoding(), 'utf-8')

        mock_stdout.encoding = 'cp65001'
        _reload()
        self.failUnlessReallyEqual(get_output_encoding(), 'utf-8')

        mock_stdout.encoding = 'koi8-r'
        _reload()
        self.failUnlessReallyEqual(get_output_encoding(), 'koi8-r')

        mock_stdout.encoding = 'nonexistent_encoding'
        self.failUnlessRaises(AssertionError, _reload)

    @patch('locale.getpreferredencoding')
    def test_get_output_encoding_not_from_stdout(self, mock_locale_getpreferredencoding):
        locale  # hush pyflakes
        mock_locale_getpreferredencoding.return_value = 'koi8-r'

        class DummyStdout:
            pass
        old_stdout = sys.stdout
        sys.stdout = DummyStdout()
        try:
            _reload()
            self.failUnlessReallyEqual(get_output_encoding(), 'koi8-r')

            sys.stdout.encoding = None
            _reload()
            self.failUnlessReallyEqual(get_output_encoding(), 'koi8-r')

            mock_locale_getpreferredencoding.return_value = None
            _reload()
            self.failUnlessReallyEqual(get_output_encoding(), 'utf-8')
        finally:
            sys.stdout = old_stdout

    @patch('sys.stdout')
    def test_argv_to_unicode(self, mock):
        mock.encoding = 'utf-8'
        _reload()

        self.failUnlessRaises(usage.UsageError,
                              argv_to_unicode,
                              lumiere_nfc.encode('latin1'))

    @patch('sys.stdout')
    def test_unicode_to_output(self, mock):
        # Encoding koi8-r cannot represent e-grave
        mock.encoding = 'koi8-r'
        _reload()
        self.failUnlessRaises(UnicodeEncodeError, unicode_to_output, lumiere_nfc)


class StringUtils(ReallyEqualMixin):
    def setUp(self):
        # Mock sys.platform because unicode_platform() uses it
        self.original_platform = sys.platform
        sys.platform = self.platform

    def tearDown(self):
        sys.platform = self.original_platform
        _reload()

    @patch('sys.stdout')
    def test_argv_to_unicode(self, mock):
        if 'argv' not in dir(self):
            return

        mock.encoding = self.output_encoding
        argu = lumiere_nfc
        argv = self.argv
        _reload()
        self.failUnlessReallyEqual(argv_to_unicode(argv), argu)

    def test_unicode_to_url(self):
        self.failUnless(unicode_to_url(lumiere_nfc), "lumi\xc3\xa8re")

    @patch('sys.stdout')
    def test_unicode_to_output(self, mock):
        if 'output' not in dir(self):
            return

        mock.encoding = self.output_encoding
        _reload()
        self.failUnlessReallyEqual(unicode_to_output(lumiere_nfc), self.output)

    def test_unicode_platform(self):
        matrix = {
          'linux2': False,
          'openbsd4': False,
          'win32':  True,
          'darwin': True,
        }

        _reload()
        self.failUnlessReallyEqual(unicode_platform(), matrix[self.platform])
 

class UbuntuKarmicUTF8(StringUtils, unittest.TestCase):
    uname = 'Linux korn 2.6.31-14-generic #48-Ubuntu SMP Fri Oct 16 14:05:01 UTC 2009 x86_64'
    output = 'lumi\xc3\xa8re'
    argv = 'lumi\xc3\xa8re'
    platform = 'linux2'
    filesystem_encoding = 'UTF-8'
    output_encoding = 'UTF-8'
    argv_encoding = 'UTF-8'

class UbuntuKarmicLatin1(StringUtils, unittest.TestCase):
    uname = 'Linux korn 2.6.31-14-generic #48-Ubuntu SMP Fri Oct 16 14:05:01 UTC 2009 x86_64'
    output = 'lumi\xe8re'
    argv = 'lumi\xe8re'
    platform = 'linux2'
    filesystem_encoding = 'ISO-8859-1'
    output_encoding = 'ISO-8859-1'
    argv_encoding = 'ISO-8859-1'

class WindowsXP(StringUtils, unittest.TestCase):
    uname = 'Windows XP 5.1.2600 x86 x86 Family 15 Model 75 Step ping 2, AuthenticAMD'
    output = 'lumi\x8are'
    platform = 'win32'
    filesystem_encoding = 'mbcs'
    output_encoding = 'cp850'
    argv_encoding = 'ascii'

class WindowsXP_UTF8(StringUtils, unittest.TestCase):
    uname = 'Windows XP 5.1.2600 x86 x86 Family 15 Model 75 Step ping 2, AuthenticAMD'
    output = 'lumi\xc3\xa8re'
    platform = 'win32'
    filesystem_encoding = 'mbcs'
    output_encoding = 'cp65001'
    argv_encoding = 'ascii'

class WindowsVista(StringUtils, unittest.TestCase):
    uname = 'Windows Vista 6.0.6000 x86 x86 Family 6 Model 15 Stepping 11, GenuineIntel'
    output = 'lumi\x8are'
    platform = 'win32'
    filesystem_encoding = 'mbcs'
    output_encoding = 'cp850'
    argv_encoding = 'ascii'

class MacOSXLeopard(StringUtils, unittest.TestCase):
    uname = 'Darwin g5.local 9.8.0 Darwin Kernel Version 9.8.0: Wed Jul 15 16:57:01 PDT 2009; root:xnu-1228.15.4~1/RELEASE_PPC Power Macintosh powerpc'
    output = 'lumi\xc3\xa8re'
    argv = 'lumi\xc3\xa8re'
    platform = 'darwin'
    filesystem_encoding = 'utf-8'
    output_encoding = 'UTF-8'
    argv_encoding = 'UTF-8'

class MacOSXLeopard7bit(StringUtils, unittest.TestCase):
    uname = 'Darwin g5.local 9.8.0 Darwin Kernel Version 9.8.0: Wed Jul 15 16:57:01 PDT 2009; root:xnu-1228.15.4~1/RELEASE_PPC Power Macintosh powerpc'
    platform = 'darwin'
    filesystem_encoding = 'utf-8'
    output_encoding = 'US-ASCII'
    argv_encoding = 'US-ASCII'

class OpenBSD(StringUtils, unittest.TestCase):
    uname = 'OpenBSD 4.1 GENERIC#187 i386 Intel(R) Celeron(R) CPU 2.80GHz ("GenuineIntel" 686-class)'
    platform = 'openbsd4'
    filesystem_encoding = '646'
    output_encoding = '646'
    argv_encoding = '646'
    # Oops, I cannot write filenames containing non-ascii characters
