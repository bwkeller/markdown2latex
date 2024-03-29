#!/usr/bin/env python
'''Extension to python-markdown to support LaTeX (rather than html) output.

Authored by Rufus Pollock: <http://www.rufuspollock.org/>

Usage:
======

1. Command Line. A script entitled markdown2latex.py is automatically
installed. For details of usage see help::

	$ markdown2latex.py -h

2. As a python-markdown extension::

	>>> import markdown
	>>> md = markdown.Markdown(None, extensions=['latex'])
	>>> # text is input string ...
	>>> latex_out = md.convert(text)

3. Directly as a module (slight inversion of std markdown extension setup)::

	>>> import markdown
	>>> import mdx_latex
	>>> md = markdown.Markdown()
	>>> latex_mdx = mdx_latex.LaTeXExtension()
	>>> latex_mdx.extendMarkdown(md)
	>>> out = md.convert(text)

History
=======

Version: 1.0 (November 15, 2006)

  * First working version (compatible with markdown 1.5)
  * Includes support for tables

Version: 1.1 (January 17, 2007)

  * Support for verbatim and images

Version: 1.2 (June 2008)

  * Refactor as an extension.
  * Make into a proper python/setuptools package.
  * Tested with markdown 1.7 but should work with 1.6 and (possibly) 1.5
	(though pre/post processor stuff not as worked out there)

Version 1.3: (July 2008)
  * Improvements to image output (width)

Version 1.3.1: (August 2009)
  * Tiny bugfix to remove duplicate keyword argument and set zip_safe=False
  * Add [width=\textwidth] by default for included images
'''
__version__ = '1.3.1'

# do some fancy importing stuff to allow use to override things in this module
# in this file while still importing * for use in our own classes
import re
import sys
import markdown
from markdown.util import etree

start_single_quote_re = re.compile("""(^|\s|")'""")
start_double_quote_re = re.compile('''(^|\s|'|`)"''')
end_double_quote_re = re.compile('"(,|\.|\s|$)')

def fix_html_blocks(text):
	out = text.replace('<ul>', '\\begin{itemize}')
	out = out.replace('</ul>', '\\end{itemize}\n')
	out = out.replace('<ol>', '\\begin{enumerate}')
	out = out.replace('</ol>', '\\end{enumerate}\n')
	out = out.replace('<sup>', '\\footnote{')
	out = out.replace('</sup>', '}')
	out = out.replace('<blockquote>', '\\begin{quotation}')
	out = out.replace('</blockquote>', '\\end{quotation}\n')
	out = out.replace('<pre><code>', '\\begin{verbatim}\n')
	out = out.replace('</code></pre>', '\\end{verbatim}\n')
	return out

def remove_html_entities(text):
	out = text.replace('&amp;', '\&')
	out = out.replace('&lt;', '<')
	out = out.replace('&gt;', '<')
	out = out.replace('&quot;', '"')
	html_tags = ['h1', 'h2', 'h3', 'h4', 'p', 'li', 'em']
	for tag in html_tags:
		out = out.replace('<%s>' % tag, '')
		out = out.replace('</%s>' % tag, '')
	return out

def escape_latex_entities(text):
	"""Escape latex reserved characters."""
	out = text
	out = remove_html_entities(out)
	out = out.replace('%', '\\%')
	out = out.replace('&', '\\&')
	out = out.replace('#', '\\#')
	out = start_single_quote_re.sub('\g<1>`', out)
	out = start_double_quote_re.sub('\g<1>``', out)
	out = end_double_quote_re.sub("''\g<1>", out)
	# people should escape these themselves as it conflicts with maths
	# out = out.replace('{', '\\{')
	# out = out.replace('}', '\\}')
	# do not do '$' here because it is dealt with by convert_maths
	# out = out.replace('$', '\\$')
	return out

def unescape_latex_entities(text):
	"""Limit ourselves as this is only used for maths stuff."""
	out = text
	out = out.replace('\\&', '&')
	return out

def makeExtension(configs=None):
	return LaTeXExtension(configs=configs)

class BlockGuru:

	def _findHead(self, lines, fn, allowBlank=0):

		"""Functional magic to help determine boundaries of indented
		   blocks.

		   @param lines: an array of strings
		   @param fn: a function that returns a substring of a string
					  if the string matches the necessary criteria
		   @param allowBlank: specifies whether it's ok to have blank
					  lines between matching functions
		   @returns: a list of post processes items and the unused
					  remainder of the original list"""

		items = []
		item = -1

		i = 0 # to keep track of where we are

		for line in lines:

			if not line.strip() and not allowBlank:
				return items, lines[i:]

			if not line.strip() and allowBlank:
				# If we see a blank line, this _might_ be the end
				i += 1

				# Find the next non-blank line
				for j in range(i, len(lines)):
					if lines[j].strip():
						next = lines[j]
						break
				else:
					# There is no more text => this is the end
					break

				# Check if the next non-blank line is still a part of the list

				part = fn(next)

				if part:
					items.append("")
					continue
				else:
					break # found end of the list

			part = fn(line)

			if part:
				items.append(part)
				i += 1
				continue
			else:
				return items, lines[i:]
		else:
			i += 1

		return items, lines[i:]


	def detabbed_fn(self, line):
		""" An auxiliary method to be passed to _findHead """
		m = re.match(r'((\t)|(    ))(.*)', line)
		if m:
			return m.group(4)
		else:
			return None


	def detectTabbed(self, lines):

		return self._findHead(lines, self.detabbed_fn,
							  allowBlank = 1)


def print_error(string):
	"""Print an error string to stderr"""
	sys.stderr.write(string +'\n')


def dequote(string):
	""" Removes quotes from around a string """
	if ( ( string.startswith('"') and string.endswith('"'))
		 or (string.startswith("'") and string.endswith("'")) ):
		return string[1:-1]
	else:
		return string

class LaTeXExtension(markdown.Extension):

	def __init__ (self, configs=None):
		self.reset()

	def extendMarkdown(self, md):
		self.md = md

		# remove escape pattern -- \\(.*) -- as this messes up any embedded
		# math and we don't need to escape stuff any more for html
		del md.inlinePatterns['escape']

		# Insert a post-processor that would actually add the footnote div
		treeprocessor = LaTeXTreeProcessor()
		md.treeprocessors['latex'] = treeprocessor

		math_pp = MathTextPostProcessor()
		table_pp = TableTextPostProcessor()
		image_pp = ImageTextPostProcessor()
		remove_html_pp = UnescapeHtmlTextPostProcessor()
		md.postprocessors['table'] = table_pp
		md.postprocessors['math'] = math_pp
		md.postprocessors['image'] = image_pp
		# run last
		md.postprocessors['remove_html'] = remove_html_pp 

		#footnote_extension = FootnoteExtension()
		#footnote_extension.extendMarkdown(md)

	def reset(self) :
		pass


class LaTeXTreeProcessor(markdown.treeprocessors.Treeprocessor):

	def run(self, root):
		'''Walk the dom converting relevant nodes to text nodes with relevant
		content.'''
		return self.tolatex(root)

	def tolatex(self, ournode, root=True):
		for elem in list(ournode):
			tags = [i.tag for i in list(elem)]
			if len(list(elem)) > 0:
				self.tolatex(elem, root=False)
			if elem.tag == 'h1':
				elem.text = '\n\\title{%s}\n' % elem.text
				elem.text += '''
% ----------------------------------------------------------------
\maketitle
% ----------------------------------------------------------------
'''
			if elem.tag == 'h2':
				elem.text = '\n\\section{%s}\n' % elem.text
			if elem.tag == 'h3':
				elem.text = '\n\\subsection{%s}\n' % elem.text
			if elem.tag == 'h4':
				elem.text = '\n\\subsubsection{%s}\n' % elem.text
			if elem.tag == 'li':
				elem.text = '''  \\item %s''' % elem.text
			if elem.tag == 'p' and not 'sup' in tags and not 'em' in tags:
				elem.text = '%s\n' % elem.text
			if elem.tag == 'em':
				elem.text = '\\emph{%s}' % elem.text


class UnescapeHtmlTextPostProcessor(markdown.postprocessors.UnescapePostprocessor):

	def run(self, text):
		print text
		text = fix_html_blocks(text)
		return remove_html_entities(text)

# ========================= MATHS =================================

class MathTextPostProcessor(markdown.postprocessors.Postprocessor):

	def run(self, instr):
		"""Convert all math sections in {text} whether latex, asciimathml or
		latexmathml formatted to latex.
		
		This assumes you are using $$ as your mathematics delimiter (*not* the
		standard asciimathml or latexmathml delimiter).
		"""
		
		def repl_1(matchobj):
			text = unescape_latex_entities(matchobj.group(1))
			tmp = text.strip()
			if tmp.startswith('\\[') or tmp.startswith('\\begin'):
				return text
			else:
				return '\\[%s\\]' % text 
		def repl_2(matchobj):
		   text = unescape_latex_entities(matchobj.group(1))
		   return '$%s$' % text
		# $$ ..... $$
		pat = re.compile('<p>\$\$([^\$]*)\$\$\s*$', re.MULTILINE)
		out = pat.sub(repl_1, instr)
		# $$ ..... $$
		pat1 = re.compile('^\$\$([^\$]*)\$\$\s*$', re.MULTILINE)
		out = pat1.sub(repl_1, out)
		# $100 million
		pat2 = re.compile('([^\$])\$([^\$])')
		out = pat2.sub('\g<1>\\$\g<2>', out)
		# Jones, $$x=3$$, is ...
		pat3 = re.compile('\$\$([^\$]*)\$\$')
		out = pat3.sub(repl_2, out)
		# Percentage signs
		out = re.sub('\%(?!\s-*)', '\\%', out)
		# some extras due to asciimathml
		out = out.replace('\\lt', '<')
		out = out.replace(' * ', ' \\cdot ')
		out = out.replace('\\del', '\\partial')
		return out



# ========================= TABLES =================================

class TableTextPostProcessor(markdown.postprocessors.Postprocessor):

	def run(self, instr):
		"""This is not very sophisticated and for it to work it is expected
		that:
			1. tables to be in a section on their own (that is at least one blank
			line above and below)
			2. no nesting of tables 
		"""
		tablematch = re.compile('<table.*</table>', re.DOTALL)
		tables = tablematch.findall(instr)
		nontables = tablematch.split(instr)
		converter = Table2Latex()
		new_blocks = []
		while len(nontables) > 0:
			new_blocks.append(nontables.pop())
			new_blocks.append(converter.convert(tables.pop()).strip())
			new_blocks.append(nontables.pop())
		new_blocks.reverse()
		return '\n'.join(new_blocks)

import xml.dom.minidom
class Table2Latex:
	"""
	Convert html tables to Latex.

	TODO: escape latex entities.
	"""

	def colformat(self):
		# centre align everything by default
		out = '|c' * self.maxcols + '|'
		return out

	def get_text(self, element):
		if element.nodeType == element.TEXT_NODE:
			return escape_latex_entities(element.data)
		result = ''
		if element.childNodes:
			for child in element.childNodes :
				text = self.get_text(child)
				if text.strip() != '':
					result += text
		return result

	def process_cell(self, element):
		# works on both td and th
		colspan = 1
		subcontent = self.get_text(element)
		buffer = ''
		if element.tagName == 'th':
			subcontent = '\\textbf{%s}' % subcontent
		if element.hasAttribute('colspan'):
			colspan = int(element.getAttribute('colspan'))
			buffer += ' \multicolumn{%s}{|c|}{%s}' % (colspan, subcontent)
		# we don't support rowspan because:
		#	1. it needs an extra latex package \usepackage{multirow}
		#	2. it requires us to mess around with the alignment tags in
		#	subsequent rows (i.e. suppose the first col in row A is rowspan 2
		#	then in row B in the latex we will need a leading &)
		# if element.hasAttribute('rowspan'):
		#	  rowspan = int(element.getAttribute('rowspan'))
		#	  buffer += ' \multirow{%s}{|c|}{%s}' % (rowspan, subcontent)
		else:
			buffer += ' %s' % subcontent
		notLast = ( element.nextSibling and
				element.nextSibling.nodeType == element.ELEMENT_NODE and
				element.nextSibling.tagName in [ 'td', 'th' ])
		if notLast:
			buffer += ' &'
		self.numcols += colspan
		return buffer

	def tolatex(self, element):
		if element.nodeType == element.TEXT_NODE:
			return ''

		buffer = ''
		subcontent = ''
		if element.childNodes:
			for child in element.childNodes :
				text = self.tolatex(child)
				if text.strip() != '':
					subcontent += text
		subcontent = subcontent.strip()

		if element.tagName == 'thead':
			buffer += '''%s
''' % subcontent

		elif element.tagName == 'tr':
			self.maxcols = max(self.numcols, self.maxcols)
			self.numcols = 0
			buffer += '\n\\hline\n%s \\\\' % subcontent

		elif element.tagName == 'td' or element.tagName == 'th':
			buffer = self.process_cell(element)
		else:
			# print '"%s"' % subcontent
			buffer += subcontent
		return buffer

	def convert(self, instr):
		self.numcols = 0
		self.maxcols = 0
		dom = xml.dom.minidom.parseString(instr)
		core = self.tolatex(dom.documentElement)

		captionElements = dom.documentElement.getElementsByTagName('caption')
		caption = ''
		if captionElements:
			caption = self.get_text(captionElements[0])
		
		colformatting = self.colformat()
		table_latex = \
'''
\\begin{table}
\\begin{tabular}{%s}
%s
\\hline
\\end{tabular}
\\\\[5pt]
\\caption{%s}
\\end{table}
''' % (colformatting, core, caption)
		return table_latex


# ========================= IMAGES =================================

class ImageTextPostProcessor(markdown.postprocessors.Postprocessor):

	def run(self, instr):
		"""Process all img tags
		
		Similar to process_tables this is not very sophisticated and for it
		to work it is expected that img tags are put in a section of their own
		(that is separated by at least one blank line above and below).
		"""
		converter = Img2Latex()
		new_blocks = []
		for block in instr.split("\n") :
			stripped = block.strip()
			stripped = stripped.replace('<p>', '')
			# <table catches modified verions (e.g. <table class="..">
			if stripped.startswith('<img'):
				latex_img = converter.convert(stripped).strip()
				new_blocks.append(latex_img)
			else :
				new_blocks.append(block)
		return '\n'.join(new_blocks)

class Img2Latex(object):

	def convert(self, instr):
		dom = xml.dom.minidom.parseString(instr)
		img = dom.documentElement
		src = img.getAttribute('src')
		alt = img.getAttribute('alt')
		out = \
'''
\\begin{figure}
\\centering
\\includegraphics[width=\\textwidth]{%s}
\\caption{%s}
\\end{figure}
''' % (src, alt)
		return out 


'''
========================= FOOTNOTES =================================

LaTeX footnote support.

Implemented via modification of original markdown approach (place footnote
definition in footnote market <sup> as opposed to putting a reference link).
'''

class FootnoteExtension (markdown.Extension):
	DEF_RE = re.compile(r'(\ ?\ ?\ ?)\[\^([^\]]*)\]:\s*(.*)')
	SHORT_USE_RE = re.compile(r'\[\^([^\]]*)\]', re.M) # [^a]

	def __init__ (self, configs=None):
		self.reset()

	def extendMarkdown(self, md):
		self.md = md

		# Stateless extensions do not need to be registered
		md.registerExtension(self)

		# Insert a preprocessor before ReferencePreprocessor
		index = md.preprocessors.index('reference')
		preprocessor = FootnotePreprocessor(self)
		preprocessor.md = md
		md.preprocessors.insert(index, 'footnote', preprocessor)

		# Insert an inline pattern before ImageReferencePattern
		FOOTNOTE_RE = r'\[\^([^\]]*)\]' # blah blah [^1] blah
		index = md.inlinePatterns.index('image_reference')
		md.inlinePatterns.insert(index, 'footnote', FootnotePattern(FOOTNOTE_RE, self))

	def reset(self) :
		self.used_footnotes={}
		self.footnotes = {}

	def setFootnote(self, id, text) :
		self.footnotes[id] = text


class FootnotePreprocessor :

	def __init__ (self, footnotes) :
		self.footnotes = footnotes

	def run(self, lines) :

		self.blockGuru = BlockGuru()
		lines = self._handleFootnoteDefinitions (lines)

		# Make a hash of all footnote marks in the text so that we
		# know in what order they are supposed to appear.  (This
		# function call doesn't really substitute anything - it's just
		# a way to get a callback for each occurence.

		text = "\n".join(lines)
		self.footnotes.SHORT_USE_RE.sub(self.recordFootnoteUse, text)

		return text.split("\n")

	def recordFootnoteUse(self, match) :

		id = match.group(1)
		id = id.strip()
		nextNum = len(self.footnotes.used_footnotes.keys()) + 1
		self.footnotes.used_footnotes[id] = nextNum


	def _handleFootnoteDefinitions(self, lines) :
		"""Recursively finds all footnote definitions in the lines.

			@param lines: a list of lines of text
			@returns: a string representing the text with footnote
					  definitions removed """

		i, id, footnote = self._findFootnoteDefinition(lines)

		if id :

			plain = lines[:i]

			detabbed, theRest = self.blockGuru.detectTabbed(lines[i+1:])

			self.footnotes.setFootnote(id,
									   footnote + "\n"
									   + "\n".join(detabbed))

			more_plain = self._handleFootnoteDefinitions(theRest)
			return plain + [""] + more_plain

		else :
			return lines

	def _findFootnoteDefinition(self, lines) :
		"""Finds the first line of a footnote definition.

			@param lines: a list of lines of text
			@returns: the index of the line containing a footnote definition """

		counter = 0
		for line in lines :
			m = self.footnotes.DEF_RE.match(line)
			if m :
				return counter, m.group(2), m.group(3)
			counter += 1
		return counter, None, None


class FootnotePattern(markdown.inlinepatterns.Pattern):

	def __init__ (self, pattern, footnotes) :
		markdown.inlinepatterns.Pattern.__init__(self, pattern)
		self.footnotes = footnotes

	def handleMatch(self, m) :
		sup = markdown.util.etree.Element('sup')
		#id = m.group(2)
		## stick the footnote text in the sup
		#self.footnotes.md._processSection(sup, self.footnotes.footnotes[id].split("\n"))
		#while self.footnotes.footnotes[id].split("\n"):
		return sup

def template(template_fo, latex_to_insert):
	tmpl = template_fo.read()
	tmpl = tmpl.replace('INSERT-TEXT-HERE', latex_to_insert)
	return tmpl
	# title_items = [ '\\title', '\\end{abstract}', '\\thanks', '\\author' ]
	# has_title_stuff = False
	# for it in title_items:
	#	 has_title_stuff = has_title_stuff or (it in tmpl)

def main():
	import optparse
	usage = \
'''usage: %prog [options] <in-file-path>

Given a file path, process it using markdown2latex and print the result on
stdout.

If using template option template should place text INSERT-TEXT-HERE in the
template where text should be inserted.
'''
	parser = optparse.OptionParser(usage)
	parser.add_option('-t', '--template', dest='template',
					  default='', help='path to latex template file (optional)')
	(options, args) = parser.parse_args()
	if not len(args) > 0:
		parser.print_help()
		sys.exit(1)
	inpath = args[0]
	infile = file(inpath)

	md = markdown.Markdown()
	mkdn2latex = LaTeXExtension()
	mkdn2latex.extendMarkdown(md)
	out = md.convert(infile.read())
	
	if options.template:
		tmpl_fo = file(options.template)
		out = template(tmpl_fo, out)

	print out
