###
# Copyright (c) 2015, Michael Daniel Telatynski <postmaster@webdevguru.co.uk>
# Copyright (c) 2015, James Lu <glolol@overdrivenetworks.com>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

###

from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircmsgs as ircmsgs
import supybot.callbacks as callbacks
import supybot.ircutils as ircutils
import supybot.ircdb as ircdb
import supybot.log as log

import re
from sys import version_info

try:
    from supybot.i18n import PluginInternationalization
    _ = PluginInternationalization('Replacer')
except ImportError:
    _ = lambda x: x

# This matches things like:
#    nick: s/abcd/xyz/
#    s/abcd/xyz/g
#    nick, s/abcd/xyz/ig
SED_REGEX = re.compile(r"^(?:(?P<nick>.+?)[:,]? )?s\/(?P<pattern>.*?)\/"
                       r"(?P<replacement>.*?)\/(?P<flags>[gi]*)?$")

class Replacer(callbacks.PluginRegexp):
    """History replacer using sed regex syntax."""
    threaded = True
    public = True
    unaddressedRegexps = ['replacer']

    @staticmethod
    def _unpack_sed(expr):
        """
        Unpacks and returns the target string, replacement string, and
        replacement count of a sed-style expression. If the "g" (global)
        flag is given, then the replacement count is set to 0.
        """
        # Delimiter for sed-style expressions is usually a "/"
        delim = '/'

        log.info("Replacer: source expression was: %s", expr)

        #if version_info[0] >= 3:  # Python 3
        #    expr = expr.encode("utf-8")

        # Unescape backslash-escaped characters.
        #escaped_expr = expr.decode('unicode_escape')
        escaped_expr = re.escape(expr)

        log.info("Replacer: escaped expression was: %s", escaped_expr)
        match = SED_REGEX.search(escaped_expr)

        if not match:  # Didn't match the SED_REGEX, abort.
            return

        # Turn the matches into a dict of named groups to data.
        groups = match.groupdict()
        pattern = groups['pattern']
        replacement = groups['replacement']

        # Get the replace expression flags, but leave it as an empty set if none
        # were given.
        raw_flags = set(groups['flags'] or ())

        flags = 0
        count = 1

        for flag in raw_flags:
            if flag == 'g':
                count = 0
            if flag == 'i':
                flags |= re.IGNORECASE

        pattern = re.compile(pattern, flags)

        return (pattern, replacement, count)

    def replacer(self, irc, msg, regex):
        if not self.registryValue('enable', msg.args[0]):
            return
        iterable = reversed(irc.state.history)
        msg.tag('Replacer')

        try:
            (pattern, replacement, count) = self._unpack_sed(msg.args[1])
        except (ValueError, re.error) as e:
            self.log.warning(_("Replacer error: %s"), e)
            if self.registryValue('displayErrors', msg.args[0]):
                irc.error(_("Replacer error: %s" % e), Raise=True)
            return

        next(iterable)
        for m in iterable:
            if m.command == 'PRIVMSG' and \
                    m.args[0] == msg.args[0]:
                target = regex.group('nick')
                if not ircutils.isNick(str(target), strictRfc=True):
                    return
                if target and m.nick != target:
                    continue

                # Don't snarf ignored users' messages unless specifically
                # told to.
                if ircdb.checkIgnored(m.prefix) and not target:
                    continue

                # When running substitutions, ignore the "* nick" part of any actions.
                action = ircmsgs.isAction(m)
                if action:
                    text = ircmsgs.unAction(m)
                else:
                    text = m.args[1]

                if self.registryValue('ignoreRegex', msg.args[0]) and \
                        m.tagged('Replacer'):
                    continue
                if m.nick == msg.nick:
                    messageprefix = msg.nick
                else:
                    messageprefix = '%s thinks %s' % (msg.nick, m.nick)
                if regexp_wrapper(text, pattern, timeout=0.05, plugin_name=self.name(),
                                  fcn_name='replacer'):
                    if self.registryValue('boldReplacementText', msg.args[0]):
                        replacement = ircutils.bold(replacement)
                    subst = process(pattern.sub, replacement,
                                text, count, timeout=0.05)
                    if action:  # If the message was an ACTION, prepend the nick back.
                        subst = '* %s %s' % (m.nick, subst)
                    irc.reply(_("%s meant to say: %s") %
                              (messageprefix, subst), prefixNick=False)
                    return

        self.log.debug(_("Replacer: Search %r not found in the last %i messages of %s."),
                         msg.args[1], len(irc.state.history), msg.args[0])
        if self.registryValue("displayErrors", msg.args[0]):
            irc.error(_("Search not found in the last %i messages.") %
                      len(irc.state.history), Raise=True)
    replacer.__doc__ = SED_REGEX.pattern

Class = Replacer


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
