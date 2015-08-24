#! /usr/bin/env python
"""
This module searches Google Scholar for articles which also cite
the references in a supplied BibTeX bibliography file
"""

import argparse
from collections import Counter
from sys import exit

try:
    import scholar
except ImportError:
    print('Error: missing required dependency')
    print('install scholar.py from https://github.com/hinnefe2/scholar.py/tree/bibcheck')
    exit()

try:
    import bibtexparser
except ImportError:
    print('Error: missing required dependency')
    print('install bibtexparser from https://github.com/sciunto/python-bibtexparser')
    exit()

class bibchecker(object):

    querier = None
    bibfile = None
    rmax = None
    bibtex_db = None
    counter = None

    def __init__(self, bibfile, rmax=50, cookie_file=None):
        # set up the scholar.py parser
        if cookie_file:
            self.load_cookie(cookie_file)

        settings = scholar.ScholarSettings()
        self.querier = scholar.ScholarQuerier()
        self.querier.apply_settings(settings)

        self.bibfile = bibfile
        self.rmax = rmax


    def do_check(self):
        """Search Google Scholar for papers relevant to those listed in a supplied BibTeX file"""
        self.load_bibfile()
        self.update_db()
        self.get_citers()
        self.find_common()

    def load_bibfile(self):
        """Load the BibTeX file"""
        assert self.bibfile is not None

        with open(self.bibfile) as bibtex_file:
            self.bibtex_db = bibtexparser.load(bibtex_file)

    def load_cookie(self, cookie_file):
        """Load a cookie file to send along with the queries"""
        scholar.ScholarConf.COOKIE_JAR_FILE = cookie_file

    def update_db(self):
        """Update the bibtex database dict with Google Scholar cluster IDs and citation counts"""
        assert self.bibtex_db is not None

        for i, article in enumerate(self.bibtex_db.entries):
            print('Trying to get cluster ID for article {}/{}'.format(i+1, len(self.bibtex_db.entries)), end='\r')
            
            query = scholar.SearchScholarQuery()
            query.set_words(article['title'])
            
            self.querier.send_query(query)
            try:
                sch_article = self.querier.articles[0]
                article['num_citations'] = sch_article.__getitem__('num_citations')
                article['cluster_id'] = sch_article.__getitem__('cluster_id')
            except IndexError:
                # in case the querier returns an empty list
                article['num_citations'] = None
                article['cluster_id'] = None

        # print newline to advance curser to next line
        print() 
        
        updated = [ref for ref in self.bibtex_db.entries if ref['cluster_id'] is not None]
        if len(updated) == 0:
            print('Error: failed to pull Google Scholar cluster IDs. Probably running into a captcha.')
            exit()

    def get_citers(self):
        """Search Google Scholar for other papers which cite the papers in the BibTeX file"""
        assert self.bibtex_db is not None

        to_check = [ref for ref in self.bibtex_db.entries if ref['cluster_id'] is not None and ref['num_citations'] < self.rmax]

        for i, ref in enumerate(to_check):
            print('Getting citations for article {}/{}'.format(i+1, len(to_check)), end='\r')
    
            # list to hold all articles which cite a particular article in the BibTeX file            
            citers  = []

            # GS only returns 20 articles at a time, have to do multiple searches 
            for start in range(0,ref['num_citations'],20):
                query = scholar.SearchScholarQuery()
                query.set_cites_id(ref['cluster_id'])
                query.set_start(start)
            
                self.querier.send_query(query)
                citers.extend(self.querier.articles)
            
            # add a list of (cluser ID, title) tuples of citing articles to the bibtex_db entry for each article
            ref['cited_by'] = [(sch_art.__getitem__('cluster_id'), sch_art.__getitem__('title')) for sch_art in citers]

        # print newline to advance curser to next line
        print() 

    def find_common(self):
        """Find most common entries among list of papers that cite the papers in the BibTeX file"""
        assert self.bibtex_db is not None

        # pull out each article for which we found other citing articles
        cited_articles = [a for a in self.bibtex_db.entries if 'cited_by' in a]

        citations_list  = []

        for article in cited_articles:
            citations_list.extend(article['cited_by'])
    
        # count how many times each article appears
        self.counter = Counter(citations_list)

    def print_results(self):
        """Print the results of the search"""
        assert self.counter is not None
        
        print('Citations shared   Title')
        for title, ct in self.counter.items():
            if ct > 1 : 
                print('{:<19}{}'.format(ct, title[1]))

    def save_results(self, outfile):
        """Save the results to (outfile)"""
        assert self.counter is not None

        with open(outfile, 'w') as o:
            for title, ct in self.counter.most_common():
                if ct > 1 : 
                    o.write(ct, title[1])
        
if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Search Google Scholar for papers which share references with a supplied BibTeX bibliography file.')

    parser.add_argument('bibfile', metavar='bibfile', type=str, help='the BibTeX (.bib) file to be parsed')
    parser.add_argument('-o', metavar='outfile', dest='outfile', type=str, help='save output to file', default=None)
    parser.add_argument('-c', metavar='cookie-file', dest='cookie_file', type=str, help='use cookies stored in file', default=None)
    parser.add_argument('-r','--rmax', metavar='N', dest='rmax', type=int, help='specify max number of references per article', default=50)

    args = parser.parse_args()

    bc = bibchecker(args.bibfile, args.rmax, args.cookie_file)
    bc.do_check()
   
    if args.outfile is not None:
        bc.save_results(args.outfile)
    else:
        bc.print_results()
