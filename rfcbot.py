#!/usr/bin/env python

import pywikibot
from pywikibot.data.sparql import SparqlQuery
import requests
import datetime
from dateutil.parser import parse
from xml.etree import ElementTree
import re

#debug
from pprint import pprint

def get_rfc_database():
	url = 'https://www.rfc-editor.org/in-notes/rfc-index.xml'
	headers = {'Accept' : 'application/xml'}
	response = requests.get(url, headers=headers)
	if response.status_code != requests.codes.ok:
		response.raise_for_status()
	root = ElementTree.fromstring(response.content)
	return root

def load_local_rfc_database():
	raw_data = ''
	with open('rfc-index.xml') as f:
		raw_data = f.read()
	root = ElementTree.fromstring(raw_data)
	return root

def parse_rfc_database(root):
	ns = {'index': 'http://www.rfc-editor.org/rfc-index'}
	rfcs = {}
	for rfc_element in root.findall('index:rfc-entry', ns):
		rfc = {}
		id_element = rfc_element.find('index:doc-id', ns)
		if id_element is None:
			print('Error: could not find doc-id element')
			continue
		rfc_id = re.sub(r'^RFC0*', r'', id_element.text)
		title_element = rfc_element.find('index:title', ns)
		if title_element is None:
			print('Error: could not find title element for rfc_id=' + rfc_id)
			continue
		rfc['title'] = title_element.text
		author_names = []
		for author_element in rfc_element.findall('index:author', ns):
			name_element = author_element.find('index:name', ns)
			if name_element is None:
				print('Error: could not find name element for rfc_id=' + rfc_id)
				continue
			author_names.append(name_element.text)
		if len(author_names) == 0:
			print('Error: count not find any author elements for rfc_id=' + rfc_id)
			continue
		rfc['authors'] = author_names
		date_element = rfc_element.find('index:date', ns)
		if date_element is None:
			print('Error: could not find date element for rfc_id=' + rfc_id)
			continue
		month_element = date_element.find('index:month', ns)
		if month_element is None:
			print('Error: could not find month element for rfc_id=' + rfc_id)
			continue
		year_element = date_element.find('index:year', ns)
		if year_element is None:
			print('Error: could not find year element for rfc_id=' + rfc_id)
			continue
		date_time = parse('1 ' + month_element.text + ' ' + year_element.text)
		rfc['date'] = date_time.isoformat('T')
		doi_element = rfc_element.find('index:doi', ns)
		if doi_element is None:
			print('Error: could not find doi element for rfc_id=' + rfc_id)
			continue
		rfc['doi'] = doi_element.text
		formats = []
		for format_element in rfc_element.findall('index:format', ns):
			format = {}
			file_format_element = format_element.find('index:file-format', ns)
			if file_format_element is None:
				print('Error: could not find file-format element for rfc_id=' + rfc_id)
				continue
			format['type'] = file_format_element.text
			page_count_element = format_element.find('index:page-count', ns)
			if page_count_element is not None:
				format['page_count'] = int(page_count_element.text)
			formats.append(format)
		rfc['formats'] = formats;
		obsoleted_by_element = rfc_element.find('index:obsoleted-by', ns)
		if obsoleted_by_element is not None:
			obsoleted_by = []
			for obsoleted_by_doc_id_element in obsoleted_by_element.findall('index:doc-id', ns):
				obsoleted_by.append(obsoleted_by_doc_id_element.text)
			if len(obsoleted_by) > 0:
				rfc['obsoleted_by'] = obsoleted_by
		obsoletes_element = rfc_element.find('index:obsoletes', ns)
		if obsoletes_element is not None:
			obsoletes = []
			for obsoletes_doc_id_element in obsoletes_element.findall('index:doc-id', ns):
				obsoletes.append(obsoletes_doc_id_element.text)
			if len(obsoletes) > 0:
				rfc['obsoletes'] = obsoletes
		updated_by_element = rfc_element.find('index:updated-by', ns)
		if updated_by_element is not None:
			updated_by = []
			for updated_by_doc_id_element in updated_by_element.findall('index:doc-id', ns):
				updated_by.append(updated_by_doc_id_element.text)
			if len(updated_by) > 0:
				rfc['updated_by'] = updated_by
		updates_element = rfc_element.find('index:updates', ns)
		if updates_element is not None:
			updates = []
			for updates_doc_id_element in updates_element.findall('index:doc-id', ns):
				updates.append(updates_doc_id_element.text)
			if len(updates) > 0:
				rfc['updates'] = updates
		rfcs[rfc_id] = rfc
	return rfcs

def get_existing_items_with_rfc_dois():
	sparqlquery = SparqlQuery()
	response = sparqlquery.query('SELECT ?doi ?item WHERE { ?item wdt:P356 ?doi . FILTER regex(?doi, \'^10.17487/RFC\\\\d{4}\') }')
	bindings = response['results']['bindings']
	existing_items = {}
	for binding in bindings:
		item_url = binding['item']['value']
		result = re.search(r'(Q\d+)', item_url)
		if not result:
			print('Error: could not find Wikidata item identifier in SPARQL results obtained by get_existing_items_with_rfc_dois()')
			continue
		item = result.group(1)
		doi = binding['doi']['value']
		result = re.search(r'RFC(\d+)', doi)
		if not result:
			print('Error: could not find RFC identifier in SPARQL results obtained by get_existing_items_with_rfc_dois()')
			continue
		rfc = result.group(1)
		existing_items[rfc] = item
	return existing_items

def match_existing_items_by_doi(rfcs):
	existing = get_existing_items_with_rfc_dois()
	for rfc, item in existing.items():
		if rfc not in rfcs:
			print('Error: probably invalid RFC identifier ' + rfc + ' detected in DOI for Wikidata item ' + item)
			continue
		rfcs[rfc]['item'] = item

def get_existing_items_with_instanceof_and_rfcnum():
	sparqlquery = SparqlQuery()
	response = sparqlquery.query('SELECT ?rfcid ?item WHERE { ?item wdt:P31 wd:Q212971 . ?item wdt:P892 ?rfcid }')
	bindings = response['results']['bindings']
	existing_items = {}
	for binding in bindings:
		item_url = binding['item']['value']
		result = re.search(r'(Q\d+)', item_url)
		if not result:
			print('Error: could not find Wikidata item identifier in SPARQL results obtained by get_existing_items_with_instanceof_and_rfcnum()')
			continue
		item = result.group(1)
		rfc = binding['rfcid']['value']
		existing_items[rfc] = item
	return existing_items

def match_existing_items_by_instanceof_and_rfcnum(rfcs):
	existing = get_existing_items_with_instanceof_and_rfcnum()
	for rfc, item in existing.items():
		if rfc not in rfcs:
			print('Error: probably invalid RFC identifier ' + rfc + ' detected for Wikidata item ' + item)
			continue
		rfcs[rfc]['item'] = item

def find_source_with_claim(repo, sources, property_id_to_find, claim_value_to_find):
	for source in sources:
		for claim_property_id, claims in source.items():
			for claim in claims:
				if claim_property_id == property_id_to_find:
					if claim.target_equals(claim_value_to_find):
						return source
	return None

def create_retrieved_claim_for_today(repo):
	now = datetime.datetime.now()
	today_date = pywikibot.WbTime(year=now.year, month=now.month, day=now.day)
	new_retrieved_claim = pywikibot.Claim(repo, 'P813')
	new_retrieved_claim.setTarget(today_date)
	return new_retrieved_claim

def add_source_for_claim(repo, claim):
	existing_sources = claim.getSources()
	rfc_editor_database_item = pywikibot.ItemPage(repo, 'Q33133762')
	source_with_required_claim = find_source_with_claim(repo, existing_sources, 'P248', rfc_editor_database_item)
	if source_with_required_claim is None:
		new_stated_in_claim = pywikibot.Claim(repo, 'P248')
		new_stated_in_claim.setTarget(rfc_editor_database_item)
		new_retrieved_claim = create_retrieved_claim_for_today(repo)
		claim.addSources([new_stated_in_claim, new_retrieved_claim])
	else:
		existing_retrieved_claim = False
		for source_property_id, source_claim in source_with_required_claim.items():
			if source_property_id == 'P813':
				existing_retrieved_claim = True
				break
		if not existing_retrieved_claim:
			new_source = source_with_required_claim
			new_retrieved_claim = create_retrieved_claim_for_today(repo)
			new_source.append(new_retrieved_claim)
			claim.removeSources(source_with_required_claim)
			claim.addSources(new_source)

def update_existing_or_create_new_claim(repo, item, existing_claims, property_id, value):
	try:
		for existing_claim in existing_claims[property_id]:
			#Special case required for wbTime as per https://doc.wikimedia.org/pywikibot/_modules/pywikibot/page.html#Claim.target_equals
			target_value = existing_claim.getTarget()
			if (isinstance(value, pywikibot.WbTime) and isinstance(target_value, pywikibot.WbTime)):
				dates_match = False
				if target_value.precision == target_value.PRECISION['year']:
					if target_value.year == value.year:
						dates_match = True
				elif target_value.precision == target_value.PRECISION['month']:
					if (target_value.year == value.year and target_value.month == value.month):
						dates_match = True
				elif target_value.precision == target_value.PRECISION['day']:
					if (target_value.year == value.year and target_value.month == value.month and target_value.day == value.day):
						dates_match = True
				if dates_match:
					add_source_for_claim(repo, existing_claim)
					return
			if existing_claim.target_equals(value):
				add_source_for_claim(repo, existing_claim)
				return
	except KeyError:
		print('Adding missing claim for property ' + property_id)
		pass
	new_claim = pywikibot.Claim(repo, property_id)
	new_claim.setTarget(value)
	item.addClaim(new_claim)
	add_source_for_claim(repo, new_claim)

def update_existing_or_create_new_claim_item(repo, item, existing_claims, property_id, target_item_id):
	value = pywikibot.ItemPage(repo, target_item_id)
	update_existing_or_create_new_claim(repo, item, existing_claims, property_id, value)

def update_existing_or_create_new_claim_monolingual_string(repo, item, existing_claims, property_id, target_language, target_text):
	value = pywikibot.WbMonolingualText(text=target_text, language=target_language)
	update_existing_or_create_new_claim(repo, item, existing_claims, property_id, value)

def update_existing_or_create_new_claim_date(repo, item, existing_claims, property_id, target_year, target_month, target_day):
	target_precision = 'day'
	if target_month is None and target_day is None:
		target_precision = 'year'
	elif target_day is None:
		target_precision = 'month'
	value = pywikibot.WbTime(year=target_year, month=target_month, day=target_day, precision=target_precision)
	update_existing_or_create_new_claim(repo, item, existing_claims, property_id, value)

def update_existing_or_create_new_claim_quantity(repo, item, existing_claims, property_id, amount, unit, error_tuple):
	site_for_creating_quantity = pywikibot.Site('wikidata', 'wikidata')
	unit_item = None
	if unit is not None:
		unit_item = pywikibot.ItemPage(repo, unit)
	value = pywikibot.WbQuantity(amount, unit_item, error_tuple, site_for_creating_quantity)
	update_existing_or_create_new_claim(repo, item, existing_claims, property_id, value)

def update_claims_for_item(repo, rfc, rfc_data, item):
	item_dict = item.get()
	existing_claims = item_dict['claims']
	processed_claims = {}
	processed_claims['instance_of'] = update_existing_or_create_new_claim_item(repo, item, existing_claims, 'P31', 'Q212971')
	processed_claims['rfc_id'] = update_existing_or_create_new_claim(repo, item, existing_claims, 'P892', rfc)
	processed_claims['title'] = update_existing_or_create_new_claim_monolingual_string(repo, item, existing_claims, 'P1476', 'en', rfc_data['title'])
	processed_claims['language_of_work'] = update_existing_or_create_new_claim_item(repo, item, existing_claims, 'P407', 'Q1860')
	processed_claims['publisher'] = update_existing_or_create_new_claim_item(repo, item, existing_claims, 'P123', 'Q217082')
	publication_year = parse(rfc_data['date']).year
	publication_month = parse(rfc_data['date']).month
	processed_claims['publication_date'] = update_existing_or_create_new_claim_date(repo, item, existing_claims, 'P577', publication_year, publication_month, None)
	processed_claims['doi'] = update_existing_or_create_new_claim(repo, item, existing_claims, 'P356', rfc_data['doi'])
	author_name_count = 0
	for author_name in rfc_data['authors']:
		author_name_count += 1
		processed_claims['author' + str(author_name_count)] = update_existing_or_create_new_claim(repo, item, existing_claims, 'P2093', author_name)
	file_format_count = 0
	for file_format in rfc_data['formats']:
		if file_format['type'] == 'ASCII':
			file_format_count += 1
			processed_claims['file_format' + str(file_format_count)] = update_existing_or_create_new_claim_item(repo, item, existing_claims, 'P2701', 'Q1145976')
			if 'page_count' in file_format:
				processed_claims['page_count'] = update_existing_or_create_new_claim_quantity(repo, item, existing_claims, 'P1104', file_format['page_count'], None, None)
			url_to_full_work_html = 'https://tools.ietf.org/html/rfc' + rfc
			processed_claims['full_work_available_at_html'] = update_existing_or_create_new_claim(repo, item, existing_claims, 'P953', url_to_full_work_html)
			url_to_full_work_txt_ietf = 'https://tools.ietf.org/rfc/rfc' + rfc + '.txt'
			processed_claims['full_work_available_at_txt_ietf'] = update_existing_or_create_new_claim(repo, item, existing_claims, 'P953', url_to_full_work_txt_ietf)
			url_to_full_work_txt_rfceditor = 'https://www.rfc-editor.org/rfc/rfc' + rfc + '.txt'
			processed_claims['full_work_available_at_txt_rfceditor'] = update_existing_or_create_new_claim(repo, item, existing_claims, 'P953', url_to_full_work_txt_rfceditor)
			url_to_full_work_pdf_ascii = 'https://www.rfc-editor.org/pdfrfc/rfc' + rfc + '.txt.pdf'
			processed_claims['full_work_available_at_pdf_ascii'] = update_existing_or_create_new_claim(repo, item, existing_claims, 'P953', url_to_full_work_pdf_ascii)
		elif file_format['type'] == 'PS':
			file_format_count += 1
			processed_claims['file_format' + str(file_format_count)] = update_existing_or_create_new_claim_item(repo, item, existing_claims, 'P2701', 'Q218170')
			url_to_full_work_ps = 'https://www.rfc-editor.org/rfc/rfc' + rfc + '.ps'
			processed_claims['full_work_available_at_ps'] = update_existing_or_create_new_claim(repo, item, existing_claims, 'P953', url_to_full_work_ps)
		elif file_format['type'] == 'PDF':
			file_format_count += 1
			processed_claims['file_format' + str(file_format_count)] = update_existing_or_create_new_claim_item(repo, item, existing_claims, 'P2701', 'Q42332')
			url_to_full_work_pdf = 'https://www.rfc-editor.org/rfc/rfc' + rfc + '.pdf'
			processed_claims['full_work_available_at_pdf'] = update_existing_or_create_new_claim(repo, item, existing_claims, 'P953', url_to_full_work_pdf)
		else:
			print('Error: unknown file format type "' + file_format[type] + '" detected for RFC' + rfc)
			continue

print('Parsing RFC database')
#rfcs = parse_rfc_database(get_rfc_database())
rfcs = parse_rfc_database(load_local_rfc_database())
#DOI lookup query is too slow for the Wikidata query service
#print('Finding existing Wikidata items via DOI property')
#match_existing_items_by_doi(rfcs)
print('Finding existing Wikidata items via RFC ID and Instance Of properties')
match_existing_items_by_instanceof_and_rfcnum(rfcs)

site = pywikibot.Site('wikidata', 'wikidata')
repo = site.data_repository()

for rfc, data in rfcs.items():
	if 'item' in rfcs[rfc]:
		item = pywikibot.ItemPage(repo, rfcs[rfc]['item'])
	else:
		continue
		print('Creating item for ' + rfc)
		new_item = pywikibot.ItemPage(repo)
		new_title = rfcs[rfc]['title']
		new_label = 'RFC ' + rfc + ': ' + new_title
		if len(new_title) >= 250 or len(new_label) >= 250:
			print('Error: could not create new item for ' + rfc + ' due to the automatically generated label being too long')
			continue
		labels = {'en': new_label}
		new_item.editLabels(labels=labels, summary='add English label: ' + new_label)
		new_description = 'request for comments publication'
		descriptions = {'en': new_description}
		new_item.editDescriptions(descriptions=descriptions, summary='add English description: ' + new_description)
		new_aliases = ['RFC' + rfc, new_title]
		aliases = {'en': new_aliases}
		new_item.editAliases(aliases=aliases, summary='add English aliases: ' + '|'.join(new_aliases))
		newid = new_item.getID()
		item = pywikibot.ItemPage(repo, newid)
	print('Processing claims for ' + rfc)
	update_claims_for_item(repo, rfc, rfcs[rfc], item)
