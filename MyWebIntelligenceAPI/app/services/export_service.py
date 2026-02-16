"""
Export Service - Port of the old crawler export functionality
Based on .crawlerOLD_APP/export.py
"""

import csv
import datetime
import re
import unicodedata
from typing import Dict, List, Optional, Any, Tuple
from textwrap import dedent
from lxml import etree
from zipfile import ZipFile
from io import StringIO
import tempfile
import os

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db.models import Land, Expression, Domain, Media
from app.crud.crud_expression import expression as expression_crud
from app.crud.crud_domain import domain as domain_crud
from app.crud.crud_media import media as media_crud


class ExportService:
    """
    Export service providing multiple export formats
    Port of the Export class from old crawler
    """
    
    GEXF_NS = {None: 'http://www.gexf.net/1.2draft', 'viz': 'http://www.gexf.net/1.1draft/viz'}
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def export_data(
        self, 
        export_type: str, 
        land_id: int, 
        minimum_relevance: int = 1,
        filename: Optional[str] = None
    ) -> Tuple[str, int]:
        """
        Main export method - proxy to specific format writers
        
        Args:
            export_type: Format type (pagecsv, fullpagecsv, nodecsv, mediacsv, pagegexf, nodegexf, corpus)
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
        if export_type.endswith('csv'):
            filename += '.csv'
        elif export_type.endswith('gexf'):
            filename += '.gexf'
        elif export_type.endswith('corpus'):
            filename += '.zip'
        
        # Create temporary file path
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, filename)
        
        # Execute export
        count = await write_method(file_path, land_id, minimum_relevance)
        
        return file_path, count
    
    async def get_sql_data(self, sql: str, column_map: Dict[str, str], land_id: int, relevance: int) -> List[Dict[str, Any]]:
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
        result = await self.db.execute(query, {"land_id": land_id, "relevance": relevance})
        
        # Convert to list of dictionaries
        rows = result.fetchall()
        return [dict(zip(column_map.keys(), row)) for row in rows]
    
    async def write_pagecsv(self, filename: str, land_id: int, minimum_relevance: int) -> int:
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
            FROM expression AS e
            JOIN domain AS d ON d.id = e.domain_id
            WHERE e.land_id = :land_id AND e.relevance >= :relevance
            ORDER BY e.id
        """
        
        data = await self.get_sql_data(sql, column_map, land_id, minimum_relevance)
        return self.write_csv_file(filename, column_map.keys(), data)
    
    async def write_fullpagecsv(self, filename: str, land_id: int, minimum_relevance: int) -> int:
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
            FROM expression AS e
            JOIN domain AS d ON d.id = e.domain_id
            WHERE e.land_id = :land_id AND e.relevance >= :relevance
            ORDER BY e.id
        """
        
        data = await self.get_sql_data(sql, column_map, land_id, minimum_relevance)
        return self.write_csv_file(filename, column_map.keys(), data)
    
    async def write_nodecsv(self, filename: str, land_id: int, minimum_relevance: int) -> int:
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
            FROM domain AS d
            JOIN expression AS e ON e.domain_id = d.id
            WHERE e.land_id = :land_id AND e.relevance >= :relevance
            GROUP BY d.id, d.name, d.title, d.description, d.keywords
            ORDER BY d.name
        """
        
        data = await self.get_sql_data(sql, column_map, land_id, minimum_relevance)
        return self.write_csv_file(filename, column_map.keys(), data)
    
    async def write_mediacsv(self, filename: str, land_id: int, minimum_relevance: int) -> int:
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
            JOIN expression AS e ON e.id = m.expression_id
            WHERE e.land_id = :land_id AND e.relevance >= :relevance
            ORDER BY m.id
        """
        
        data = await self.get_sql_data(sql, column_map, land_id, minimum_relevance)
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
    
    async def write_pagegexf(self, filename: str, land_id: int, minimum_relevance: int) -> int:
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
            FROM expression AS e
            JOIN domain AS d ON d.id = e.domain_id
            WHERE e.land_id = :land_id AND e.relevance >= :relevance
            ORDER BY e.id
        """
        
        node_data = await self.get_sql_data(sql, node_map, land_id, minimum_relevance)
        
        for row in node_data:
            self.add_gexf_node(row, nodes, gexf_attributes, ('url', 'relevance'))
            count += 1
        
        # Get edges (links between expressions)
        edge_map = {
            'source_id': 'link.source_id',
            'source_domain_id': 'e1.domain_id',
            'target_id': 'link.target_id',
            'target_domain_id': 'e2.domain_id'
        }
        
        # Note: This assumes a link table exists - may need adjustment based on actual schema
        edge_sql = """
            WITH valid_expressions AS (
                SELECT id, domain_id
                FROM expression
                WHERE land_id = :land_id AND relevance >= :relevance
            )
            SELECT
                {}
            FROM link AS link
            JOIN valid_expressions AS e1 ON e1.id = link.source_id
            JOIN valid_expressions AS e2 ON e2.id = link.target_id
            WHERE e1.domain_id != e2.domain_id
        """
        
        try:
            edge_data = await self.get_sql_data(edge_sql, edge_map, land_id, minimum_relevance)
            for row in edge_data:
                self.add_gexf_edge([row['source_id'], row['target_id'], 1], edges)
        except Exception:
            # If link table doesn't exist, skip edges
            pass
        
        # Write GEXF file
        tree = etree.ElementTree(gexf)
        tree.write(filename, xml_declaration=True, pretty_print=True, encoding='utf-8')
        
        return count
    
    async def write_nodegexf(self, filename: str, land_id: int, minimum_relevance: int) -> int:
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
            FROM domain AS d
            JOIN expression AS e ON e.domain_id = d.id
            WHERE e.land_id = :land_id AND e.relevance >= :relevance
            GROUP BY d.id, d.name, d.title, d.description, d.keywords
        """
        
        node_data = await self.get_sql_data(sql, node_map, land_id, minimum_relevance)
        
        for row in node_data:
            self.add_gexf_node(row, nodes, gexf_attributes, ('name', 'average_relevance'))
            count += 1
        
        # Add domain-to-domain edges based on links
        edge_map = {
            'source_domain_id': 'e1.domain_id',
            'target_domain_id': 'e2.domain_id',
            'weight': 'COUNT(*)'
        }
        
        edge_sql = """
            WITH valid_expressions AS (
                SELECT id, domain_id
                FROM expression
                WHERE land_id = :land_id AND relevance >= :relevance
            )
            SELECT
                {}
            FROM link AS link
            JOIN valid_expressions AS e1 ON e1.id = link.source_id
            JOIN valid_expressions AS e2 ON e2.id = link.target_id
            WHERE e1.domain_id != e2.domain_id
            GROUP BY e1.domain_id, e2.domain_id
        """
        
        try:
            edge_data = await self.get_sql_data(edge_sql, edge_map, land_id, minimum_relevance)
            for row in edge_data:
                self.add_gexf_edge([row['source_domain_id'], row['target_domain_id'], row['weight']], edges)
        except Exception:
            # If link table doesn't exist, skip edges
            pass
        
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
    
    async def write_corpus(self, filename: str, land_id: int, minimum_relevance: int) -> int:
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
            FROM expression AS e
            JOIN domain AS d ON d.id = e.domain_id
            WHERE e.land_id = :land_id AND e.relevance >= :relevance
            ORDER BY e.id
        """
        
        data = await self.get_sql_data(sql, column_map, land_id, minimum_relevance)
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
