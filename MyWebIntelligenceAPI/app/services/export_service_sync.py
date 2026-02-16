"""
Synchronous Export Service for Celery tasks
Since Celery workers run in synchronous context, we need a sync version
"""

import csv
import datetime
import re
import unicodedata
from typing import Dict, List, Optional, Any, Tuple
from textwrap import dedent
from lxml import etree
from zipfile import ZipFile
import tempfile
import os

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.models import Land, Expression, Domain, Media


class SyncExportService:
    """
    Synchronous export service for Celery tasks
    Port of the Export class from old crawler with sync database operations
    """
    
    GEXF_NS = {None: 'http://www.gexf.net/1.2draft', 'viz': 'http://www.gexf.net/1.1draft/viz'}
    
    def __init__(self, db: Session):
        self.db = db
    
    # Export types that produce a ZIP file
    ZIP_EXPORT_TYPES = {'corpus', 'nodelinkcsv'}

    def export_data(
        self,
        export_type: str,
        land_id: int,
        minimum_relevance: int = 1,
        filename: Optional[str] = None
    ) -> Tuple[str, int]:
        """
        Main export method - proxy to specific format writers

        Args:
            export_type: Format type (pagecsv, fullpagecsv, nodecsv, mediacsv,
                         pagegexf, nodegexf, corpus, nodelinkcsv,
                         pseudolinks, pseudolinkspage, pseudolinksdomain,
                         tagmatrix, tagcontent)
            land_id: Land ID to export
            minimum_relevance: Minimum relevance filter
            filename: Optional filename (auto-generated if not provided)

        Returns:
            Tuple of (file_path, record_count)
        """
        if not filename:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"export_{export_type}_{land_id}_{timestamp}"

        # Get the appropriate write method
        write_method = getattr(self, f'write_{export_type}')

        # Add appropriate file extension
        if export_type in self.ZIP_EXPORT_TYPES:
            filename += '.zip'
        elif export_type.endswith('gexf'):
            filename += '.gexf'
        elif export_type.endswith('csv') or export_type in (
            'pseudolinks', 'pseudolinkspage', 'pseudolinksdomain',
            'tagmatrix', 'tagcontent',
        ):
            filename += '.csv'

        # Create temporary file path
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, filename)

        # Execute export
        count = write_method(file_path, land_id, minimum_relevance)

        return file_path, count
    
    def get_sql_data(self, sql: str, column_map: Dict[str, str], land_id: int, relevance: int) -> List[Dict[str, Any]]:
        """
        Execute SQL query and return results as list of dictionaries
        
        Args:
            sql: SQL query template with {} placeholder for columns
            column_map: Mapping of result columns to SQL expressions
            land_id: Land ID parameter
            relevance: Minimum relevance parameter
            
        Returns:
            List of dictionaries with query results
        """
        # Build column list
        cols = ",\n".join([f"{sql_expr} AS {col_name}" for col_name, sql_expr in column_map.items()])
        
        # Execute query
        query = text(sql.format(cols))
        result = self.db.execute(query, {"land_id": land_id, "relevance": relevance})
        
        # Convert to list of dictionaries
        rows = result.fetchall()
        return [dict(zip(column_map.keys(), row)) for row in rows]
    
    def write_pagecsv(self, filename: str, land_id: int, minimum_relevance: int) -> int:
        """
        Write page CSV export - basic page information
        """
        column_map = {
            'id': 'e.id',
            'url': 'e.url',
            'title': 'e.title',
            'description': 'e.description',
            'keywords': 'e.keywords',
            'relevance': 'e.relevance',
            'depth': 'e.depth',
            'domain_id': 'e.domain_id',
            'domain_name': 'd.name',
            'domain_description': 'd.description',
            'domain_keywords': 'd.keywords'
        }
        
        sql = """
            SELECT
                {}
            FROM expressions AS e
            JOIN domains AS d ON d.id = e.domain_id
            WHERE e.land_id = :land_id AND e.relevance >= :relevance
            ORDER BY e.id
        """

        data = self.get_sql_data(sql, column_map, land_id, minimum_relevance)
        return self.write_csv_file(filename, column_map.keys(), data)

    def write_fullpagecsv(self, filename: str, land_id: int, minimum_relevance: int) -> int:
        """
        Write full page CSV export - includes readable content
        """
        column_map = {
            'id': 'e.id',
            'url': 'e.url',
            'title': 'e.title',
            'description': 'e.description',
            'keywords': 'e.keywords',
            'readable': 'e.readable',
            'relevance': 'e.relevance',
            'depth': 'e.depth',
            'domain_id': 'e.domain_id',
            'domain_name': 'd.name',
            'domain_description': 'd.description',
            'domain_keywords': 'd.keywords'
        }
        
        sql = """
            SELECT
                {}
            FROM expressions AS e
            JOIN domains AS d ON d.id = e.domain_id
            WHERE e.land_id = :land_id AND e.relevance >= :relevance
            ORDER BY e.id
        """

        data = self.get_sql_data(sql, column_map, land_id, minimum_relevance)
        return self.write_csv_file(filename, column_map.keys(), data)

    def write_nodecsv(self, filename: str, land_id: int, minimum_relevance: int) -> int:
        """
        Write domain/node CSV export - aggregated domain statistics
        """
        column_map = {
            'id': 'd.id',
            'name': 'd.name',
            'title': 'd.title',
            'description': 'd.description',
            'keywords': 'd.keywords',
            'expressions': 'COUNT(*)',
            'average_relevance': 'ROUND(AVG(e.relevance), 2)'
        }
        
        sql = """
            SELECT
                {}
            FROM domains AS d
            JOIN expressions AS e ON e.domain_id = d.id
            WHERE e.land_id = :land_id AND e.relevance >= :relevance
            GROUP BY d.id, d.name, d.title, d.description, d.keywords
            ORDER BY d.name
        """

        data = self.get_sql_data(sql, column_map, land_id, minimum_relevance)
        return self.write_csv_file(filename, column_map.keys(), data)

    def write_mediacsv(self, filename: str, land_id: int, minimum_relevance: int) -> int:
        """
        Write media CSV export
        """
        column_map = {
            'id': 'm.id',
            'expression_id': 'm.expression_id',
            'url': 'm.url',
            'type': 'm.type'
        }
        
        sql = """
            SELECT
                {}
            FROM media AS m
            JOIN expressions AS e ON e.id = m.expression_id
            WHERE e.land_id = :land_id AND e.relevance >= :relevance
            ORDER BY m.id
        """
        
        data = self.get_sql_data(sql, column_map, land_id, minimum_relevance)
        return self.write_csv_file(filename, column_map.keys(), data)
    
    def write_csv_file(self, filename: str, headers: List[str], data: List[Dict[str, Any]]) -> int:
        """
        Write CSV file from data
        
        Args:
            filename: Output filename
            headers: CSV headers
            data: List of dictionaries with data
            
        Returns:
            Number of records written
        """
        count = 0
        with open(filename, 'w', newline='\n', encoding="utf-8") as file:
            writer = csv.writer(file, quoting=csv.QUOTE_ALL)
            
            # Write header
            writer.writerow(headers)
            
            # Write data
            for row_dict in data:
                row = [str(row_dict.get(header, '')) for header in headers]
                writer.writerow(row)
                count += 1
        
        return count
    
    def write_pagegexf(self, filename: str, land_id: int, minimum_relevance: int) -> int:
        """
        Write page GEXF export for network visualization
        """
        count = 0
        gexf_attributes = [
            ('title', 'string'),
            ('description', 'string'),
            ('keywords', 'string'),
            ('domain_id', 'string'),
            ('relevance', 'integer'),
            ('depth', 'integer')
        ]
        
        gexf, nodes, edges = self.get_gexf_structure(gexf_attributes)
        
        # Get nodes (expressions)
        node_map = {
            'id': 'e.id',
            'url': 'e.url',
            'title': 'e.title',
            'description': 'e.description',
            'keywords': 'e.keywords',
            'relevance': 'e.relevance',
            'depth': 'e.depth',
            'domain_id': 'e.domain_id',
            'domain_name': 'd.name',
            'domain_title': 'd.title',
            'domain_description': 'd.description',
            'domain_keywords': 'd.keywords'
        }
        
        sql = """
            SELECT
                {}
            FROM expressions AS e
            JOIN domains AS d ON d.id = e.domain_id
            WHERE e.land_id = :land_id AND e.relevance >= :relevance
            ORDER BY e.id
        """

        node_data = self.get_sql_data(sql, node_map, land_id, minimum_relevance)

        for row in node_data:
            self.add_gexf_node(row, nodes, gexf_attributes, ('url', 'relevance'))
            count += 1
        
        # Write GEXF file (skip edges for now since link table may not exist)
        tree = etree.ElementTree(gexf)
        tree.write(filename, xml_declaration=True, pretty_print=True, encoding='utf-8')
        
        return count
    
    def write_nodegexf(self, filename: str, land_id: int, minimum_relevance: int) -> int:
        """
        Write domain/node GEXF export for network visualization
        """
        count = 0
        gexf_attributes = [
            ('title', 'string'),
            ('description', 'string'),
            ('keywords', 'string'),
            ('expressions', 'integer'),
            ('average_relevance', 'float')
        ]
        
        gexf, nodes, edges = self.get_gexf_structure(gexf_attributes)
        
        # Get nodes (domains)
        node_map = {
            'id': 'd.id',
            'name': 'd.name',
            'title': 'd.title',
            'description': 'd.description',
            'keywords': 'd.keywords',
            'expressions': 'COUNT(*)',
            'average_relevance': 'ROUND(AVG(e.relevance), 2)'
        }
        
        sql = """
            SELECT
                {}
            FROM domains AS d
            JOIN expressions AS e ON e.domain_id = d.id
            WHERE e.land_id = :land_id AND e.relevance >= :relevance
            GROUP BY d.id, d.name, d.title, d.description, d.keywords
        """

        node_data = self.get_sql_data(sql, node_map, land_id, minimum_relevance)
        
        for row in node_data:
            self.add_gexf_node(row, nodes, gexf_attributes, ('name', 'average_relevance'))
            count += 1
        
        # Write GEXF file
        tree = etree.ElementTree(gexf)
        tree.write(filename, xml_declaration=True, pretty_print=True, encoding='utf-8')
        
        return count
    
    def get_gexf_structure(self, attributes: List[Tuple[str, str]]):
        """
        Initialize GEXF XML structure
        
        Args:
            attributes: List of (name, type) tuples for node attributes
            
        Returns:
            Tuple of (gexf_root, nodes_element, edges_element)
        """
        date = datetime.datetime.now().strftime("%Y-%m-%d")
        gexf = etree.Element(
            'gexf',
            nsmap=self.GEXF_NS,
            attrib={'version': '1.2'}
        )
        
        etree.SubElement(
            gexf,
            'meta',
            attrib={'lastmodifieddate': date, 'creator': 'MyWebIntelligence'}
        )
        
        graph = etree.SubElement(
            gexf,
            'graph',
            attrib={'mode': 'static', 'defaultedgetype': 'directed'}
        )
        
        attr = etree.SubElement(
            graph,
            'attributes',
            attrib={'class': 'node'}
        )
        
        for i, (name, attr_type) in enumerate(attributes):
            etree.SubElement(
                attr,
                'attribute',
                attrib={'id': str(i), 'title': name, 'type': attr_type}
            )
        
        nodes = etree.SubElement(graph, 'nodes')
        edges = etree.SubElement(graph, 'edges')
        
        return gexf, nodes, edges
    
    def add_gexf_edge(self, values: List[Any], edges):
        """
        Add an edge to GEXF structure
        
        Args:
            values: [source_id, target_id, weight]
            edges: GEXF edges element
        """
        source_id, target_id, weight = values
        etree.SubElement(
            edges,
            'edge',
            attrib={
                'id': f"{source_id}_{target_id}",
                'source': str(source_id),
                'target': str(target_id),
                'weight': str(weight)
            }
        )
    
    def add_gexf_node(self, row: Dict[str, Any], nodes, attributes: List[Tuple[str, str]], keys: Tuple[str, str]):
        """
        Add a node to GEXF structure
        
        Args:
            row: Node data dictionary
            nodes: GEXF nodes element
            attributes: List of (name, type) tuples
            keys: Tuple of (label_key, size_key)
        """
        label_key, size_key = keys
        node = etree.SubElement(
            nodes,
            'node',
            attrib={'id': str(row['id']), 'label': str(row.get(label_key, ''))}
        )
        
        etree.SubElement(
            node,
            '{%s}size' % self.GEXF_NS['viz'],
            attrib={'value': str(row.get(size_key, 1))}
        )
        
        attvalues = etree.SubElement(node, 'attvalues')
        
        for i, (attr_name, _) in enumerate(attributes):
            value = row.get(attr_name, '')
            if value is not None:
                etree.SubElement(
                    attvalues,
                    'attvalue',
                    attrib={'for': str(i), 'value': str(value)}
                )
    
    def write_corpus(self, filename: str, land_id: int, minimum_relevance: int) -> int:
        """
        Write corpus ZIP export with individual text files
        """
        column_map = {
            'id': 'e.id',
            'url': 'e.url',
            'title': 'e.title',
            'description': 'e.description',
            'readable': 'e.readable',
            'domain': 'd.name'
        }
        
        sql = """
            SELECT
                {}
            FROM expressions AS e
            JOIN domains AS d ON d.id = e.domain_id
            WHERE e.land_id = :land_id AND e.relevance >= :relevance
            ORDER BY e.id
        """

        data = self.get_sql_data(sql, column_map, land_id, minimum_relevance)
        count = 0

        with ZipFile(filename, 'w') as archive:
            for row in data:
                count += 1
                file_title = self.slugify(row.get('title', ''))
                archive_filename = f"{row['id']}-{file_title}.txt"
                
                # Create file content with metadata header
                metadata = self.create_metadata(row)
                content = metadata + (row.get('readable', '') or '')
                
                archive.writestr(archive_filename, content)
        
        return count
    
    def slugify(self, string: str) -> str:
        """
        Convert string to URL-safe slug
        """
        if not string:
            return 'untitled'
        
        slug = unicodedata.normalize('NFKD', str(string))
        slug = slug.encode('ascii', 'ignore').decode('ascii').lower()
        slug = re.sub(r'[^a-z0-9]+', '-', slug).strip('-')
        slug = re.sub(r'[-]+', '-', slug)
        
        return slug[:50] if slug else 'untitled'
    
    def create_metadata(self, row: Dict[str, Any]) -> str:
        """
        Create metadata header for corpus files
        """
        metadata = """\
            ---
            Title: "{title}"
            Creator: ""
            Contributor: ""
            Coverage: ""
            Date: ""
            Description: "{description}"
            Subject: ""
            Type: ""
            Format: ""
            Identifier: "{id}"
            Language: ""
            Publisher: "{domain}"
            Relation: ""
            Rights: ""
            Source: "{url}"
            ---
            
        """.format(
            title=row.get('title', ''),
            description=row.get('description', ''),
            id=row.get('id', ''),
            domain=row.get('domain', ''),
            url=row.get('url', '')
        )
        
        return dedent(metadata)

    # ─────────────────────────────────────────────────────────
    # nodelinkcsv : 4 CSV files (pagesnodes, pageslinks, domainnodes, domainlinks)
    # ─────────────────────────────────────────────────────────

    def write_nodelinkcsv(self, filename: str, land_id: int, minimum_relevance: int) -> int:
        """Export 4 CSV files for complete network analysis, bundled in a ZIP.

        Files inside the archive:
        - pagesnodes.csv   (expressions with seorank JSON expanded)
        - pageslinks.csv   (expression-level links)
        - domainnodes.csv  (aggregated domain stats)
        - domainlinks.csv  (inter-domain link counts)
        """
        import io
        import json

        def _csv_bytes(headers, rows):
            """Write CSV to an in-memory bytes buffer."""
            buf = io.StringIO()
            writer = csv.writer(buf, quoting=csv.QUOTE_ALL)
            writer.writerow(headers)
            for r in rows:
                writer.writerow(r)
            return buf.getvalue().encode("utf-8")

        params = {"land_id": land_id, "relevance": minimum_relevance}

        # ── 1. pagesnodes ──────────────────────────────────────
        pn_sql = text("""
            SELECT
                e.id, e.url, e.domain_id, d.name AS domain_name,
                e.title, e.description, e.keywords,
                e."language" AS lang, e.relevance, e.depth, e.http_status,
                e.created_at, e.published_at, e.crawled_at, e.approved_at, e.readable_at,
                e.validllm, e.validmodel, e.seorank
            FROM expressions AS e
            JOIN domains AS d ON d.id = e.domain_id
            WHERE e.land_id = :land_id AND e.relevance >= :relevance
            ORDER BY e.id
        """)
        rows = self.db.execute(pn_sql, params).fetchall()
        pn_base_headers = [
            "id", "url", "domain_id", "domain_name", "title", "description", "keywords",
            "lang", "relevance", "depth", "http_status",
            "created_at", "published_at", "crawled_at", "approved_at", "readable_at",
            "validllm", "validmodel",
        ]
        seorank_keys: list = []
        parsed_rows: list = []
        for row in rows:
            d = dict(zip(pn_base_headers + ["seorank_raw"], row))
            sr_raw = d.pop("seorank_raw", None)
            sr_data = {}
            if sr_raw:
                try:
                    sr_data = json.loads(sr_raw) if isinstance(sr_raw, str) else (sr_raw if isinstance(sr_raw, dict) else {})
                except Exception:
                    pass
            for k in sr_data:
                if k not in seorank_keys:
                    seorank_keys.append(k)
            d["_sr"] = sr_data
            parsed_rows.append(d)

        all_headers = pn_base_headers + seorank_keys
        pn_rows = []
        for d in parsed_rows:
            vals = [d.get(h, "") for h in pn_base_headers]
            vals += [d["_sr"].get(k, "na") for k in seorank_keys]
            pn_rows.append(vals)
        count = len(pn_rows)

        # ── 2. pageslinks ─────────────────────────────────────
        pl_sql = text("""
            SELECT
                el.source_id, es.url AS source_url, es.domain_id AS source_domain_id,
                el.target_id, et.url AS target_url, et.domain_id AS target_domain_id
            FROM expression_links AS el
            JOIN expressions AS es ON es.id = el.source_id
            JOIN expressions AS et ON et.id = el.target_id
            WHERE es.land_id = :land_id AND es.relevance >= :relevance
            ORDER BY el.source_id
        """)
        pl_rows = self.db.execute(pl_sql, params).fetchall()
        pl_headers = ["source_id", "source_url", "source_domain_id",
                       "target_id", "target_url", "target_domain_id"]

        # ── 3. domainnodes ────────────────────────────────────
        dn_sql = text("""
            SELECT
                d.id, d.name, d.title, d.description, d.http_status,
                COUNT(e.id) AS nbexpressions,
                ROUND(AVG(e.relevance)::numeric, 2) AS average_relevance,
                MIN(e.created_at) AS first_expression_date,
                MAX(e.created_at) AS last_expression_date
            FROM domains AS d
            JOIN expressions AS e ON e.domain_id = d.id
            WHERE e.land_id = :land_id AND e.relevance >= :relevance
            GROUP BY d.id
            ORDER BY d.id
        """)
        dn_rows = self.db.execute(dn_sql, params).fetchall()
        dn_headers = ["id", "name", "title", "description", "http_status",
                       "nbexpressions", "average_relevance",
                       "first_expression_date", "last_expression_date"]

        # ── 4. domainlinks ────────────────────────────────────
        dl_sql = text("""
            SELECT
                es.domain_id AS source_domain_id, ds.name AS source_domain_name,
                et.domain_id AS target_domain_id, dt.name AS target_domain_name,
                COUNT(*) AS link_count
            FROM expression_links AS el
            JOIN expressions AS es ON es.id = el.source_id
            JOIN expressions AS et ON et.id = el.target_id
            JOIN domains AS ds ON ds.id = es.domain_id
            JOIN domains AS dt ON dt.id = et.domain_id
            WHERE es.land_id = :land_id AND es.relevance >= :relevance
              AND es.domain_id != et.domain_id
            GROUP BY es.domain_id, ds.name, et.domain_id, dt.name
            ORDER BY link_count DESC
        """)
        dl_rows = self.db.execute(dl_sql, params).fetchall()
        dl_headers = ["source_domain_id", "source_domain_name",
                       "target_domain_id", "target_domain_name", "link_count"]

        # ── Bundle into ZIP ───────────────────────────────────
        with ZipFile(filename, "w") as zf:
            zf.writestr("pagesnodes.csv", _csv_bytes(all_headers, pn_rows))
            zf.writestr("pageslinks.csv", _csv_bytes(pl_headers, pl_rows))
            zf.writestr("domainnodes.csv", _csv_bytes(dn_headers, dn_rows))
            zf.writestr("domainlinks.csv", _csv_bytes(dl_headers, dl_rows))

        return count

    # ─────────────────────────────────────────────────────────
    # pseudolinks exports (require paragraph_similarity table from embeddings)
    # ─────────────────────────────────────────────────────────

    def write_pseudolinks(self, filename: str, land_id: int, minimum_relevance: int) -> int:
        """Export paragraph-level semantic similarity pairs."""
        sql = text("""
            SELECT
                s.paragraph1_id AS source_paragraph_id,
                s.paragraph2_id AS target_paragraph_id,
                s.similarity_score AS relation_score,
                s.method,
                LEFT(p1.text, 200) AS source_text,
                LEFT(p2.text, 200) AS target_text,
                e1.id AS source_expression_id,
                e2.id AS target_expression_id
            FROM similarities AS s
            JOIN paragraphs AS p1 ON p1.id = s.paragraph1_id
            JOIN paragraphs AS p2 ON p2.id = s.paragraph2_id
            JOIN expressions AS e1 ON e1.id = p1.expression_id
            JOIN expressions AS e2 ON e2.id = p2.expression_id
            WHERE e1.land_id = :land_id
              AND e1.relevance >= :relevance
              AND e2.land_id = e1.land_id
            ORDER BY s.similarity_score DESC
        """)
        try:
            rows = self.db.execute(sql, {"land_id": land_id, "relevance": minimum_relevance}).fetchall()
        except Exception:
            rows = []
        headers = ["Source_ParagraphID", "Target_ParagraphID", "SimilarityScore",
                    "Method", "Source_Text", "Target_Text",
                    "Source_ExpressionID", "Target_ExpressionID"]
        return self._write_rows_csv(filename, headers, rows)

    def write_pseudolinkspage(self, filename: str, land_id: int, minimum_relevance: int) -> int:
        """Export page-level aggregated semantic links."""
        sql = text("""
            SELECT
                CASE WHEN e1.id <= e2.id THEN e1.id ELSE e2.id END AS source_expression_id,
                CASE WHEN e1.id <= e2.id THEN e2.id ELSE e1.id END AS target_expression_id,
                CASE WHEN e1.id <= e2.id THEN e1.domain_id ELSE e2.domain_id END AS source_domain_id,
                CASE WHEN e1.id <= e2.id THEN e2.domain_id ELSE e1.domain_id END AS target_domain_id,
                COUNT(*) AS pair_count,
                ROUND(AVG(s.similarity_score)::numeric, 6) AS avg_similarity,
                MIN(s.similarity_score) AS min_similarity,
                MAX(s.similarity_score) AS max_similarity
            FROM similarities AS s
            JOIN paragraphs AS p1 ON p1.id = s.paragraph1_id
            JOIN paragraphs AS p2 ON p2.id = s.paragraph2_id
            JOIN expressions AS e1 ON e1.id = p1.expression_id
            JOIN expressions AS e2 ON e2.id = p2.expression_id
            WHERE e1.land_id = :land_id
              AND e1.relevance >= :relevance
              AND e2.land_id = e1.land_id
              AND e1.id != e2.id
            GROUP BY
              CASE WHEN e1.id <= e2.id THEN e1.id ELSE e2.id END,
              CASE WHEN e1.id <= e2.id THEN e2.id ELSE e1.id END,
              CASE WHEN e1.id <= e2.id THEN e1.domain_id ELSE e2.domain_id END,
              CASE WHEN e1.id <= e2.id THEN e2.domain_id ELSE e1.domain_id END
            ORDER BY pair_count DESC
        """)
        try:
            rows = self.db.execute(sql, {"land_id": land_id, "relevance": minimum_relevance}).fetchall()
        except Exception:
            rows = []
        headers = ["Source_ExpressionID", "Target_ExpressionID", "Source_DomainID",
                    "Target_DomainID", "PairCount", "AvgSimilarity",
                    "MinSimilarity", "MaxSimilarity"]
        return self._write_rows_csv(filename, headers, rows)

    def write_pseudolinksdomain(self, filename: str, land_id: int, minimum_relevance: int) -> int:
        """Export domain-level aggregated semantic links."""
        sql = text("""
            SELECT
                CASE WHEN e1.domain_id <= e2.domain_id THEN e1.domain_id ELSE e2.domain_id END AS source_domain_id,
                CASE WHEN e1.domain_id <= e2.domain_id THEN d1.name ELSE d2.name END AS source_domain,
                CASE WHEN e1.domain_id <= e2.domain_id THEN e2.domain_id ELSE e1.domain_id END AS target_domain_id,
                CASE WHEN e1.domain_id <= e2.domain_id THEN d2.name ELSE d1.name END AS target_domain,
                COUNT(*) AS pair_count,
                ROUND(AVG(s.similarity_score)::numeric, 6) AS avg_similarity,
                MIN(s.similarity_score) AS min_similarity,
                MAX(s.similarity_score) AS max_similarity
            FROM similarities AS s
            JOIN paragraphs AS p1 ON p1.id = s.paragraph1_id
            JOIN paragraphs AS p2 ON p2.id = s.paragraph2_id
            JOIN expressions AS e1 ON e1.id = p1.expression_id
            JOIN expressions AS e2 ON e2.id = p2.expression_id
            JOIN domains AS d1 ON d1.id = e1.domain_id
            JOIN domains AS d2 ON d2.id = e2.domain_id
            WHERE e1.land_id = :land_id
              AND e1.relevance >= :relevance
              AND e2.land_id = e1.land_id
              AND e1.domain_id != e2.domain_id
            GROUP BY
              CASE WHEN e1.domain_id <= e2.domain_id THEN e1.domain_id ELSE e2.domain_id END,
              CASE WHEN e1.domain_id <= e2.domain_id THEN d1.name ELSE d2.name END,
              CASE WHEN e1.domain_id <= e2.domain_id THEN e2.domain_id ELSE e1.domain_id END,
              CASE WHEN e1.domain_id <= e2.domain_id THEN d2.name ELSE d1.name END
            ORDER BY pair_count DESC
        """)
        try:
            rows = self.db.execute(sql, {"land_id": land_id, "relevance": minimum_relevance}).fetchall()
        except Exception:
            rows = []
        headers = ["Source_DomainID", "Source_Domain", "Target_DomainID", "Target_Domain",
                    "PairCount", "AvgSimilarity", "MinSimilarity", "MaxSimilarity"]
        return self._write_rows_csv(filename, headers, rows)

    # ─────────────────────────────────────────────────────────
    # Tag exports
    # ─────────────────────────────────────────────────────────

    def write_tagmatrix(self, filename: str, land_id: int, minimum_relevance: int) -> int:
        """Export tag co-occurrence matrix."""
        sql = text("""
            WITH RECURSIVE tag_path AS (
                SELECT id, name::text AS path
                FROM tags
                WHERE parent_id IS NULL AND land_id = :land_id
                UNION ALL
                SELECT t.id, tp.path || '_' || t.name
                FROM tag_path AS tp
                JOIN tags AS t ON tp.id = t.parent_id
            )
            SELECT tc.expression_id, tp.path, COUNT(*) AS cnt
            FROM tags AS t
            JOIN tag_path AS tp ON tp.id = t.id
            JOIN tagged_content AS tc ON tc.tag_id = t.id
            JOIN expressions AS e ON e.id = tc.expression_id
            WHERE t.land_id = :land_id AND e.relevance >= :relevance
            GROUP BY tc.expression_id, tp.path
            ORDER BY tc.expression_id, t.parent_id, t.sorting
        """)
        try:
            rows = self.db.execute(sql, {"land_id": land_id, "relevance": minimum_relevance}).fetchall()
        except Exception:
            rows = []

        # Build matrix
        tags_list: list = []
        data_rows: list = []
        for row in rows:
            if row[1] not in tags_list:
                tags_list.append(row[1])
            data_rows.append(row)

        matrix: Dict[int, Dict[str, int]] = {}
        for row in data_rows:
            eid = row[0]
            if eid not in matrix:
                matrix[eid] = {t: 0 for t in tags_list}
            matrix[eid][row[1]] = row[2]

        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(["expression_id"] + tags_list)
            for eid, data in matrix.items():
                writer.writerow([eid] + [data.get(t, 0) for t in tags_list])

        return len(matrix)

    def write_tagcontent(self, filename: str, land_id: int, minimum_relevance: int) -> int:
        """Export tagged content snippets."""
        sql = text("""
            WITH RECURSIVE tag_path AS (
                SELECT id, name::text AS path
                FROM tags
                WHERE parent_id IS NULL AND land_id = :land_id
                UNION ALL
                SELECT t.id, tp.path || '_' || t.name
                FROM tag_path AS tp
                JOIN tags AS t ON tp.id = t.parent_id
            )
            SELECT tp.path, tc.text, tc.expression_id
            FROM tagged_content AS tc
            JOIN tags AS t ON t.id = tc.tag_id
            JOIN tag_path AS tp ON tp.id = t.id
            JOIN expressions AS e ON e.id = tc.expression_id
            WHERE t.land_id = :land_id AND e.relevance >= :relevance
            ORDER BY t.parent_id, t.sorting
        """)
        try:
            rows = self.db.execute(sql, {"land_id": land_id, "relevance": minimum_relevance}).fetchall()
        except Exception:
            rows = []
        headers = ["path", "content", "expression_id"]
        return self._write_rows_csv(filename, headers, rows)

    # ─────────────────────────────────────────────────────────
    # Helper
    # ─────────────────────────────────────────────────────────

    def _write_rows_csv(self, filename: str, headers: list, rows: list) -> int:
        """Write rows to CSV file."""
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(headers)
            for row in rows:
                writer.writerow(row)
        return len(rows)