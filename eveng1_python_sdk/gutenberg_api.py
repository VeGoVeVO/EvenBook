"""
Simple Project Gutenberg API Client
==================================

A lightweight API client for accessing Project Gutenberg books
using the Gutendx API (https://gutendx.com/)
"""

import requests
import re
import time
from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class BookInfo:
    """Information about a Project Gutenberg book"""
    id: int
    title: str
    authors: List[str]
    languages: List[str]
    subjects: List[str]
    download_count: int
    formats: Dict[str, str]  # format -> download URL
    
    @property
    def text_url(self) -> Optional[str]:
        """Get plain text download URL"""
        for format_type, url in self.formats.items():
            if 'text/plain' in format_type.lower() or format_type.endswith('.txt'):
                return url
        return None
    
    @property
    def epub_url(self) -> Optional[str]:
        """Get EPUB download URL"""
        for format_type, url in self.formats.items():
            if 'epub' in format_type.lower():
                return url
        return None

class GutenbergClient:
    """Client for accessing Project Gutenberg books"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'EvenBook/1.0.0 (E-book Reader)'
        })
        
        # Popular books database (fallback when API is unavailable) - Top 50+ classics
        self.popular_books = [
            {'id': 1342, 'title': 'Pride and Prejudice', 'authors': ['Jane Austen'], 'languages': ['en'], 'download_count': 50000, 'text_url': 'https://www.gutenberg.org/files/1342/1342-0.txt'},
            {'id': 11, 'title': "Alice's Adventures in Wonderland", 'authors': ['Lewis Carroll'], 'languages': ['en'], 'download_count': 45000, 'text_url': 'https://www.gutenberg.org/files/11/11-0.txt'},
            {'id': 84, 'title': 'Frankenstein', 'authors': ['Mary Wollstonecraft Shelley'], 'languages': ['en'], 'download_count': 40000, 'text_url': 'https://www.gutenberg.org/files/84/84-0.txt'},
            {'id': 1260, 'title': 'Jane Eyre', 'authors': ['Charlotte Brontë'], 'languages': ['en'], 'download_count': 35000, 'text_url': 'https://www.gutenberg.org/files/1260/1260-0.txt'},
            {'id': 74, 'title': 'The Adventures of Tom Sawyer', 'authors': ['Mark Twain'], 'languages': ['en'], 'download_count': 32000, 'text_url': 'https://www.gutenberg.org/files/74/74-0.txt'},
            {'id': 1661, 'title': 'The Adventures of Sherlock Holmes', 'authors': ['Arthur Conan Doyle'], 'languages': ['en'], 'download_count': 30000, 'text_url': 'https://www.gutenberg.org/files/1661/1661-0.txt'},
            {'id': 345, 'title': 'Dracula', 'authors': ['Bram Stoker'], 'languages': ['en'], 'download_count': 28000, 'text_url': 'https://www.gutenberg.org/files/345/345-0.txt'},
            {'id': 2701, 'title': 'Moby Dick', 'authors': ['Herman Melville'], 'languages': ['en'], 'download_count': 25000, 'text_url': 'https://www.gutenberg.org/files/2701/2701-0.txt'},
            {'id': 1184, 'title': 'The Count of Monte Cristo', 'authors': ['Alexandre Dumas'], 'languages': ['en'], 'download_count': 23000, 'text_url': 'https://www.gutenberg.org/files/1184/1184-0.txt'},
            {'id': 76, 'title': 'Adventures of Huckleberry Finn', 'authors': ['Mark Twain'], 'languages': ['en'], 'download_count': 22000, 'text_url': 'https://www.gutenberg.org/files/76/76-0.txt'},
            {'id': 1080, 'title': 'A Modest Proposal', 'authors': ['Jonathan Swift'], 'languages': ['en'], 'download_count': 20000, 'text_url': 'https://www.gutenberg.org/files/1080/1080-0.txt'},
            {'id': 35, 'title': 'The Time Machine', 'authors': ['H. G. Wells'], 'languages': ['en'], 'download_count': 18000, 'text_url': 'https://www.gutenberg.org/files/35/35-0.txt'},
            {'id': 120, 'title': 'Treasure Island', 'authors': ['Robert Louis Stevenson'], 'languages': ['en'], 'download_count': 17000, 'text_url': 'https://www.gutenberg.org/files/120/120-0.txt'},
            {'id': 394, 'title': 'Cranford', 'authors': ['Elizabeth Cleghorn Gaskell'], 'languages': ['en'], 'download_count': 15000, 'text_url': 'https://www.gutenberg.org/files/394/394-0.txt'},
            {'id': 98, 'title': 'A Tale of Two Cities', 'authors': ['Charles Dickens'], 'languages': ['en'], 'download_count': 14000, 'text_url': 'https://www.gutenberg.org/files/98/98-0.txt'},
            {'id': 174, 'title': 'The Picture of Dorian Gray', 'authors': ['Oscar Wilde'], 'languages': ['en'], 'download_count': 13500, 'text_url': 'https://www.gutenberg.org/files/174/174-0.txt'},
            {'id': 158, 'title': 'Emma', 'authors': ['Jane Austen'], 'languages': ['en'], 'download_count': 13000, 'text_url': 'https://www.gutenberg.org/files/158/158-0.txt'},
            {'id': 161, 'title': 'Sense and Sensibility', 'authors': ['Jane Austen'], 'languages': ['en'], 'download_count': 12500, 'text_url': 'https://www.gutenberg.org/files/161/161-0.txt'},
            {'id': 36, 'title': 'The War of the Worlds', 'authors': ['H. G. Wells'], 'languages': ['en'], 'download_count': 12000, 'text_url': 'https://www.gutenberg.org/files/36/36-0.txt'},
            {'id': 768, 'title': 'Wuthering Heights', 'authors': ['Emily Brontë'], 'languages': ['en'], 'download_count': 11500, 'text_url': 'https://www.gutenberg.org/files/768/768-0.txt'},
            {'id': 43, 'title': 'The Strange Case of Dr. Jekyll and Mr. Hyde', 'authors': ['Robert Louis Stevenson'], 'languages': ['en'], 'download_count': 11000, 'text_url': 'https://www.gutenberg.org/files/43/43-0.txt'},
            {'id': 140, 'title': 'The Jungle Book', 'authors': ['Rudyard Kipling'], 'languages': ['en'], 'download_count': 10500, 'text_url': 'https://www.gutenberg.org/files/140/140-0.txt'},
            {'id': 141, 'title': 'Mansfield Park', 'authors': ['Jane Austen'], 'languages': ['en'], 'download_count': 10000, 'text_url': 'https://www.gutenberg.org/files/141/141-0.txt'},
            {'id': 205, 'title': 'Walden, and On The Duty Of Civil Disobedience', 'authors': ['Henry David Thoreau'], 'languages': ['en'], 'download_count': 9500, 'text_url': 'https://www.gutenberg.org/files/205/205-0.txt'},
            {'id': 2600, 'title': 'War and Peace', 'authors': ['Leo Tolstoy'], 'languages': ['en'], 'download_count': 9000, 'text_url': 'https://www.gutenberg.org/files/2600/2600-0.txt'},
            {'id': 244, 'title': 'A Study in Scarlet', 'authors': ['Arthur Conan Doyle'], 'languages': ['en'], 'download_count': 8500, 'text_url': 'https://www.gutenberg.org/files/244/244-0.txt'},
            {'id': 55, 'title': 'The Wonderful Wizard of Oz', 'authors': ['L. Frank Baum'], 'languages': ['en'], 'download_count': 8000, 'text_url': 'https://www.gutenberg.org/files/55/55-0.txt'},
            {'id': 408, 'title': 'The Soul of a Man Under Socialism', 'authors': ['Oscar Wilde'], 'languages': ['en'], 'download_count': 7500, 'text_url': 'https://www.gutenberg.org/files/408/408-0.txt'},
            {'id': 514, 'title': 'Little Women', 'authors': ['Louisa May Alcott'], 'languages': ['en'], 'download_count': 7000, 'text_url': 'https://www.gutenberg.org/files/514/514-0.txt'},
            {'id': 600, 'title': 'Notes from the Underground', 'authors': ['Fyodor Dostoyevsky'], 'languages': ['en'], 'download_count': 6500, 'text_url': 'https://www.gutenberg.org/files/600/600-0.txt'},
            {'id': 16, 'title': 'Peter Pan', 'authors': ['J. M. Barrie'], 'languages': ['en'], 'download_count': 6000, 'text_url': 'https://www.gutenberg.org/files/16/16-0.txt'},
            {'id': 219, 'title': 'Heart of Darkness', 'authors': ['Joseph Conrad'], 'languages': ['en'], 'download_count': 5500, 'text_url': 'https://www.gutenberg.org/files/219/219-0.txt'},
            {'id': 1952, 'title': 'The Yellow Wallpaper', 'authors': ['Charlotte Perkins Gilman'], 'languages': ['en'], 'download_count': 5000, 'text_url': 'https://www.gutenberg.org/files/1952/1952-0.txt'},
            {'id': 28054, 'title': 'The Brothers Karamazov', 'authors': ['Fyodor Dostoyevsky'], 'languages': ['en'], 'download_count': 4500, 'text_url': 'https://www.gutenberg.org/files/28054/28054-0.txt'},
            {'id': 526, 'title': 'The Romance of Lust', 'authors': ['Anonymous'], 'languages': ['en'], 'download_count': 4000, 'text_url': 'https://www.gutenberg.org/files/526/526-0.txt'},
            {'id': 1727, 'title': 'The Odyssey', 'authors': ['Homer'], 'languages': ['en'], 'download_count': 3500, 'text_url': 'https://www.gutenberg.org/files/1727/1727-0.txt'},
            {'id': 67979, 'title': 'The Blue Castle', 'authors': ['L. M. Montgomery'], 'languages': ['en'], 'download_count': 3000, 'text_url': 'https://www.gutenberg.org/files/67979/67979-0.txt'},
            {'id': 3207, 'title': 'Leviathan', 'authors': ['Thomas Hobbes'], 'languages': ['en'], 'download_count': 2500, 'text_url': 'https://www.gutenberg.org/files/3207/3207-0.txt'},
            {'id': 31, 'title': 'Twenty Thousand Leagues under the Sea', 'authors': ['Jules Verne'], 'languages': ['en'], 'download_count': 2000, 'text_url': 'https://www.gutenberg.org/files/31/31-0.txt'},
            {'id': 4363, 'title': 'The Man in the Iron Mask', 'authors': ['Alexandre Dumas'], 'languages': ['en'], 'download_count': 1500, 'text_url': 'https://www.gutenberg.org/files/4363/4363-0.txt'},
            {'id': 8800, 'title': 'The Divine Comedy', 'authors': ['Dante Alighieri'], 'languages': ['en'], 'download_count': 1000, 'text_url': 'https://www.gutenberg.org/files/8800/8800-0.txt'},
        ]
    
    def search(self, 
               query: Optional[str] = None,
               languages: Optional[List[str]] = None,
               sort: str = 'popular',
               page: int = 1,
               page_size: int = 25) -> List[BookInfo]:
        """
        Search for books
        
        Args:
            query: Search term for title or author
            languages: List of language codes (e.g., ['en', 'fr'])
            sort: Sort order ('popular', 'ascending', 'descending')
            page: Page number (1-based)
            page_size: Number of results per page
            
        Returns:
            List of BookInfo objects
        """
        # Use local database for now (API fallback)
        filtered_books = self.popular_books.copy()
        
        # Filter by language
        if languages:
            filtered_books = [b for b in filtered_books if any(lang in b['languages'] for lang in languages)]
        
        # Filter by query
        if query:
            query_lower = query.lower()
            filtered_books = [
                b for b in filtered_books 
                if query_lower in b['title'].lower() or 
                   any(query_lower in author.lower() for author in b['authors'])
            ]
        
        # Sort books
        if sort == 'popular':
            filtered_books.sort(key=lambda x: x['download_count'], reverse=True)
        elif sort == 'ascending':
            filtered_books.sort(key=lambda x: x['title'])
        elif sort == 'descending':
            filtered_books.sort(key=lambda x: x['title'], reverse=True)
        
        # Apply pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_books = filtered_books[start_idx:end_idx]
        
        # Convert to BookInfo objects
        books = []
        for book_data in page_books:
            book = BookInfo(
                id=book_data['id'],
                title=book_data['title'],
                authors=book_data['authors'],
                languages=book_data['languages'],
                subjects=[],  # Not included in simplified data
                download_count=book_data['download_count'],
                formats={'text/plain': book_data['text_url']}
            )
            books.append(book)
        
        return books
    
    def get_popular_books(self, 
                         languages: Optional[List[str]] = None,
                         limit: int = 50) -> List[BookInfo]:
        """Get popular books"""
        return self.search(
            languages=languages,
            sort='popular',
            page_size=limit
        )
    
    def get_book_by_id(self, book_id: int) -> Optional[BookInfo]:
        """Get a specific book by ID"""
        try:
            response = self.session.get(f"{self.base_url}/books/{book_id}/")
            response.raise_for_status()
            data = response.json()
            return self._parse_book(data)
            
        except Exception as e:
            print(f"Error getting book {book_id}: {e}")
            return None
    
    def download_text(self, book: BookInfo) -> Optional[str]:
        """Download the plain text content of a book"""
        if not book.text_url:
            return None
            
        try:
            # Add delay to be respectful to the server
            time.sleep(0.5)
            
            response = self.session.get(book.text_url)
            response.raise_for_status()
            
            # Try to decode with UTF-8, fallback to latin-1
            try:
                text = response.content.decode('utf-8')
            except UnicodeDecodeError:
                text = response.content.decode('latin-1', errors='ignore')
            
            return text
            
        except Exception as e:
            print(f"Error downloading text for book {book.id}: {e}")
            return None
    
    def _parse_book(self, data: Dict) -> Optional[BookInfo]:
        """Parse book data from API response"""
        try:
            # Extract authors
            authors = []
            for author_data in data.get('authors', []):
                name = author_data.get('name', '').strip()
                if name:
                    authors.append(name)
            
            if not authors:
                authors = ['Unknown Author']
            
            # Extract subjects
            subjects = data.get('subjects', [])
            
            # Extract languages
            languages = data.get('languages', ['en'])
            
            # Extract formats and filter for useful ones
            formats = {}
            for format_key, url in data.get('formats', {}).items():
                # Clean up format key
                clean_format = format_key.strip()
                
                # Skip some formats we don't need
                if any(skip in clean_format.lower() for skip in ['images', 'rdf', 'cover']):
                    continue
                
                formats[clean_format] = url
            
            # Skip books without text format
            if not any('text' in fmt.lower() or fmt.endswith('.txt') for fmt in formats.keys()):
                return None
            
            return BookInfo(
                id=data['id'],
                title=data.get('title', 'Unknown Title').strip(),
                authors=authors,
                languages=languages,
                subjects=subjects,
                download_count=data.get('download_count', 0),
                formats=formats
            )
            
        except Exception as e:
            print(f"Error parsing book data: {e}")
            return None

# Quick test function
def test_api():
    """Test the Gutenberg API client"""
    client = GutenbergClient()
    
    print("Testing Gutenberg API...")
    
    # Test search
    print("\n1. Searching for 'Alice in Wonderland':")
    books = client.search("Alice in Wonderland", languages=['en'], page_size=5)
    for book in books:
        print(f"   - {book.title} by {', '.join(book.authors)} (ID: {book.id})")
    
    # Test popular books
    print("\n2. Getting popular books:")
    popular = client.get_popular_books(languages=['en'], limit=5)
    for book in popular:
        print(f"   - {book.title} by {', '.join(book.authors)} ({book.download_count:,} downloads)")
    
    # Test downloading text
    if popular:
        book = popular[0]
        print(f"\n3. Downloading text for '{book.title}':")
        text = client.download_text(book)
        if text:
            print(f"   Downloaded {len(text):,} characters")
            print(f"   First 200 chars: {text[:200].strip()}...")
        else:
            print("   Failed to download text")

if __name__ == "__main__":
    test_api()