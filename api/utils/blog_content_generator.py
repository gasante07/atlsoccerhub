"""
Blog Content Generator
Scalable system for generating rich HTML content for blog posts
"""

import json
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


def _load_site_branding() -> tuple:
    """siteName and hubMarketingName from site.config.json (fallbacks for API-only runs)."""
    try:
        root = Path(__file__).resolve().parent.parent.parent
        with open(root / "src" / "config" / "site.config.json", encoding="utf-8") as f:
            site = json.load(f)
        name = (site.get("brand") or {}).get("siteName") or "Atlanta Soccer Hub"
        hub = (site.get("hubMarketingName") or "").strip() or "Metro Atlanta"
        return name, hub
    except Exception:
        return "Atlanta Soccer Hub", "Metro Atlanta"


SITE_NAME, HUB_MARKETING_DEFAULT = _load_site_branding()


class BlogContentGenerator:
    """Generates SEO-optimized blog content for different blog types"""
    
    def __init__(self, sport_config: Dict):
        self.sport_config = sport_config
        self.cities = sport_config.get("cities", [])
        self.keywords = sport_config.get("keywords", {})
        self.quick_facts = sport_config.get("quickFacts", {})
        self.faq_templates = sport_config.get("faqTemplates", [])

    def _venue_blurb(self, venue: str) -> str:
        """Short venue copy from name heuristics (no hardcoded other markets)."""
        v = (venue or "").strip()
        if not v:
            return "Local parks and rented fields are the backbone of pickup soccer in the area."
        low = v.lower()
        if "indoor" in low or "turf" in low or "bubble" in low:
            return f"{v} is a strong option when heat, storms, or night games call for reliable turf or indoor space—confirm split fees with the organizer."
        if "park" in low:
            return f"{v} is a go-to outdoor option in Metro Atlanta—check lighting, parking, and whether the run is on grass or turf."
        if "complex" in low or "center" in low or "centre" in low:
            return f"{v} often books by the hour for small-sided games—popular weeknights fill fast, so RSVP early."
        return f"{v} is one of many places players use around Metro Atlanta—ask the organizer about surface, cost split, and skill level."
    
    def generate_content(self, post: Dict, blog_type: str, location_context: Dict = None) -> str:
        """
        Generate full HTML content for a blog post
        
        Args:
            post: Blog post dictionary with title, excerpt, etc.
            blog_type: Type of blog post ('country', 'city', 'area')
            location_context: Context dict with city, area_name, etc.
        
        Returns:
            HTML string with full blog post content
        """
        location_context = location_context or {}
        
        # Route to appropriate content generator
        if blog_type == "country":
            return self._generate_country_content(post, location_context)
        elif blog_type == "city":
            return self._generate_city_content(post, location_context)
        elif blog_type == "area":
            return self._generate_area_content(post, location_context)
        else:
            return self._generate_generic_content(post, location_context)
    
    def _generate_country_content(self, post: Dict, context: Dict) -> str:
        """Generate content for country-level blog posts"""
        title = post.get("title", "")
        excerpt = post.get("excerpt", "")
        
        # Determine content based on title
        if "ultimate guide" in title.lower() or "guide" in title.lower():
            return self._generate_ultimate_guide_content(post, context)
        elif "5-a-side" in title.lower() and "vs" in title.lower():
            return self._generate_comparison_content(post, context)
        else:
            return self._generate_generic_guide_content(post, context)
    
    def _generate_city_content(self, post: Dict, context: Dict) -> str:
        """Generate content for city-level blog posts"""
        city_name = context.get("city", HUB_MARKETING_DEFAULT)
        title = post.get("title", "")
        
        # Get city-specific data
        city_data = self._get_city_data(city_name)
        
        if "best places" in title.lower() or "places to play" in title.lower():
            return self._generate_venues_guide_content(post, context, city_data)
        elif "culture" in title.lower():
            return self._generate_culture_guide_content(post, context, city_data)
        else:
            return self._generate_city_generic_content(post, context, city_data)
    
    def _generate_area_content(self, post: Dict, context: Dict) -> str:
        """Generate content for area-level blog posts"""
        area_name = context.get("area_name", "")
        city_name = context.get("city_name", "")
        
        return self._generate_area_guide_content(post, context, area_name, city_name)
    
    def _generate_ultimate_guide_content(self, post: Dict, context: Dict) -> str:
        """Generate comprehensive guide content"""
        sections = [
            self._generate_intro_section(post),
            self._generate_what_is_section(),
            self._generate_types_of_games_section(),
            self._generate_how_to_find_section(),
            self._generate_how_to_organise_section(),
            self._generate_cost_section(),
            self._generate_tips_section(),
            self._generate_conclusion_section(post)
        ]
        return "\n\n".join(sections)
    
    def _generate_comparison_content(self, post: Dict, context: Dict) -> str:
        """Generate comparison content (5-a-side vs 7-a-side vs 11-a-side)"""
        sections = [
            self._generate_intro_section(post),
            self._generate_comparison_table_section(),
            self._generate_5aside_details_section(),
            self._generate_7aside_details_section(),
            self._generate_11aside_details_section(),
            self._generate_which_to_choose_section(),
            self._generate_conclusion_section(post)
        ]
        return "\n\n".join(sections)
    
    def _generate_venues_guide_content(self, post: Dict, context: Dict, city_data: Dict) -> str:
        """Generate venue guide content for a city"""
        city_name = context.get("city", "")
        venues = city_data.get("localReferences", {}).get(
            "venues",
            ["regional sports complexes", "county parks", "local facilities"],
        )
        
        sections = [
            self._generate_intro_section(post, city_name),
            self._generate_venues_overview_section(city_name, venues),
            self._generate_venue_details_section(venues),
            self._generate_booking_tips_section(),
            self._generate_local_venues_section(city_name, venues),
            self._generate_conclusion_section(post, city_name)
        ]
        return "\n\n".join(sections)
    
    def _generate_culture_guide_content(self, post: Dict, context: Dict, city_data: Dict) -> str:
        """Generate culture guide content for a city"""
        city_name = context.get("city", "")
        teams = city_data.get("localReferences", {}).get("teams", [])
        culture = city_data.get("localReferences", {}).get("culture", "")
        
        sections = [
            self._generate_intro_section(post, city_name),
            self._generate_city_football_history_section(city_name, teams),
            self._generate_local_teams_section(teams),
            self._generate_football_scene_section(city_name, culture),
            self._generate_joining_community_section(city_name),
            self._generate_conclusion_section(post, city_name)
        ]
        return "\n\n".join(sections)
    
    def _generate_area_guide_content(self, post: Dict, context: Dict, area_name: str, city_name: str) -> str:
        """Generate guide content for an area"""
        sections = [
            self._generate_intro_section(post, f"{area_name}, {city_name}"),
            self._generate_area_overview_section(area_name, city_name),
            self._generate_finding_games_area_section(area_name, city_name),
            self._generate_organising_area_section(area_name, city_name),
            self._generate_local_community_section(area_name, city_name),
            self._generate_conclusion_section(post, f"{area_name}, {city_name}")
        ]
        return "\n\n".join(sections)
    
    # Content section generators
    
    def _generate_intro_section(self, post: Dict, location: str = None) -> str:
        """Generate introduction section"""
        loc = location if location is not None else HUB_MARKETING_DEFAULT
        excerpt = post.get("excerpt", "")
        return f'''<p class="blog-intro">{excerpt}</p>
<p>Whether you're looking to get back into soccer, find a regular pickup game, or organize your own games, this guide has everything you need to know about pickup soccer in {loc}.</p>'''
    
    def _generate_what_is_section(self) -> str:
        """Generate 'What is pickup soccer' section"""
        return '''<h2>What is Pickup Soccer?</h2>
<p>Pickup soccer is all about getting together with other players for a game without the commitment of joining a formal league or club. It's flexible, social, and accessible to players of all abilities.</p>
<p>Most casual games are:</p>
<ul>
    <li><strong>5v5</strong> - The most popular format, played on smaller fields (usually turf or indoor)</li>
    <li><strong>7v7</strong> - A bit bigger, often played on larger fields</li>
    <li><strong>11v11</strong> - Full-size games, less common for casual play</li>
</ul>
<p>The beauty of pickup soccer is that it's organized by players, for players. You can show up when it suits you, meet new people, and enjoy a game without the pressure of competitive leagues.</p>'''
    
    def _generate_types_of_games_section(self) -> str:
        """Generate types of games section"""
        return '''<h2>Types of Casual Football Games</h2>
<p>There are several formats you'll come across when looking for casual football:</p>

<h3>5-a-Side</h3>
<p>5-a-side is by far the most popular format for casual games. It's fast-paced, requires fewer players (10 total), and is usually played on smaller pitches at facilities like Powerleague or Goals. Perfect for after-work kickabouts or weekend games.</p>

<h3>7-a-Side</h3>
<p>7-a-side offers a bit more space and is great if you want something between 5-a-side and full-size. You'll need 14 players total, and games are often played on larger pitches or local facilities.</p>

<h3>11-a-Side</h3>
<p>Full-size football is less common for casual games but you'll find some groups organising regular 11-a-side kickabouts. These require 22 players and are usually played on local pitches or sports centres.</p>

<h3>Kickabouts</h3>
<p>Some games are just informal kickabouts - no strict format, just players getting together for a game. These are often the most relaxed and beginner-friendly.</p>'''
    
    def _generate_how_to_find_section(self) -> str:
        """Generate how to find games section"""
        return f'''<h2>How to Find Casual Football Games</h2>
<p>Finding a kickabout near you is easier than ever:</p>

<h3>1. Sign Up to {SITE_NAME}</h3>
<p>Join {SITE_NAME} with your email and area, and you'll be notified when new games go live in your neighborhood. It's free and takes seconds.</p>

<h3>2. Browse Available Games</h3>
<p>Once you're signed up, you can browse games organized by other players in your area. Filter by date, time, location, and ability level to find the perfect match.</p>

<h3>3. Check Local Facilities</h3>
<p>Many regional complexes and county parks have online reservations or regular slots where organizers post games—check venue sites and local soccer groups.</p>

<h3>4. Ask Around</h3>
<p>Don't underestimate the power of word-of-mouth. Ask colleagues, friends, or check local Facebook groups and community boards.</p>'''
    
    def _generate_how_to_organise_section(self) -> str:
        """Generate how to organise section"""
        return f'''<h2>How to Organise Your Own Game</h2>
<p>Want to start your own regular kickabout? Here's how:</p>

<h3>1. Choose Your Format</h3>
<p>Decide whether you want 5-a-side, 7-a-side, or 11-a-side. 5-a-side is usually easiest to fill and most popular.</p>

<h3>2. Find a Venue</h3>
<p>Book a pitch at a local facility like Powerleague or Goals, or use a local sports centre or pitch. Most venues allow online booking.</p>

<h3>3. Set a Regular Time</h3>
<p>Consistency helps build a regular group. Many successful games run at the same time each week - evenings (6-9pm) and weekends are most popular.</p>

<h3>4. Split the Cost</h3>
<p>Pitch costs typically range from £30-£60 per hour for 5-a-side. Split this between players - usually £3-£8 per person depending on the venue and number of players.</p>

<h3>5. Post Your Game</h3>
<p>Let {SITE_NAME} know you're organizing, and we'll help you set up your game listing. Players in your area will be notified and can sign up.</p>

<h3>6. Build Your Group</h3>
<p>Start with a core group of friends or colleagues, then let it grow organically. Regular games often develop into tight-knit communities.</p>'''
    
    def _generate_cost_section(self) -> str:
        """Generate cost section"""
        return '''<h2>How Much Does It Cost?</h2>
<p>Costs vary depending on the venue and location:</p>

<ul>
    <li><strong>5-a-side facilities</strong> (Powerleague, Goals): £30-£60 per hour, split between players (£3-£8 per person)</li>
    <li><strong>Local pitches</strong>: Often cheaper, sometimes £20-£40 per hour</li>
    <li><strong>Indoor facilities</strong>: Similar to outdoor 5-a-side, sometimes slightly more expensive</li>
</ul>

<p>Most organizers will let you know the cost upfront when you sign up. The organizer usually books the field and players split the cost on the day.</p>

<p>Some groups have a kitty system where regular players pay monthly, making it easier to manage costs and ensure consistent attendance.</p>'''
    
    def _generate_tips_section(self) -> str:
        """Generate tips section"""
        return '''<h2>Tips for Getting the Most Out of Casual Football</h2>

<h3>For Players</h3>
<ul>
    <li><strong>Be reliable</strong> - If you sign up, turn up. Organisers rely on confirmed numbers.</li>
    <li><strong>Communicate</strong> - Let organisers know if you can't make it with plenty of notice.</li>
    <li><strong>Bring the basics</strong> - Football boots (or trainers for 3G), shin pads, water, and a change of clothes.</li>
    <li><strong>Be friendly</strong> - Pickup soccer is social. Introduce yourself and enjoy meeting new people.</li>
    <li><strong>Respect the level</strong> - Check if it's beginner-friendly, intermediate, or competitive before signing up.</li>
</ul>

<h3>For Organisers</h3>
<ul>
    <li><strong>Set clear expectations</strong> - Let players know the ability level, cost, and what to bring.</li>
    <li><strong>Confirm numbers</strong> - Check in with players a day or two before to ensure you have enough.</li>
    <li><strong>Have backups</strong> - Keep a list of players who can fill in at short notice.</li>
    <li><strong>Be consistent</strong> - Regular games build stronger communities.</li>
    <li><strong>Split costs fairly</strong> - Be transparent about pitch costs and how you're splitting them.</li>
</ul>'''
    
    def _generate_comparison_table_section(self) -> str:
        """Generate comparison table section"""
        return '''<h2>5-a-Side vs 7-a-Side vs 11-a-Side: Quick Comparison</h2>
<table class="blog-comparison-table">
    <thead>
        <tr>
            <th>Format</th>
            <th>Players</th>
            <th>Pitch Size</th>
            <th>Best For</th>
            <th>Typical Cost</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><strong>5-a-Side</strong></td>
            <td>10 (5 per team)</td>
            <td>Small (usually 3G/astro)</td>
            <td>After-work games, quick kickabouts</td>
            <td>£3-£8 per person</td>
        </tr>
        <tr>
            <td><strong>7-a-Side</strong></td>
            <td>14 (7 per team)</td>
            <td>Medium</td>
            <td>Weekend games, more space</td>
            <td>£4-£10 per person</td>
        </tr>
        <tr>
            <td><strong>11-a-Side</strong></td>
            <td>22 (11 per team)</td>
            <td>Full-size</td>
            <td>Traditional football experience</td>
            <td>£5-£12 per person</td>
        </tr>
    </tbody>
</table>'''
    
    def _generate_5aside_details_section(self) -> str:
        """Generate 5-a-side details section"""
        return '''<h2>5-a-Side: The Most Popular Choice</h2>
<p>5-a-side is the go-to format for casual football, and for good reason:</p>

<h3>Why Choose 5-a-Side?</h3>
<ul>
    <li><strong>Easier to organise</strong> - Only need 10 players total</li>
    <li><strong>More touches</strong> - With fewer players, everyone gets more involved</li>
    <li><strong>Faster pace</strong> - Quick, intense games perfect for fitness</li>
    <li><strong>Widely available</strong> - Most facilities cater to 5-a-side</li>
    <li><strong>Flexible</strong> - Can play with 8-12 players if numbers fluctuate</li>
</ul>

<h3>What to Expect</h3>
<p>5-a-side games are usually played on smaller pitches (often 3G or astro turf) at dedicated facilities. Games typically last 40-60 minutes, with short breaks. The pace is fast, and it's great for improving your touch and fitness.</p>

<p>Most 5-a-side games are mixed ability, though some organisers specify beginner-friendly or competitive levels. Check the game description before signing up.</p>'''
    
    def _generate_7aside_details_section(self) -> str:
        """Generate 7-a-side details section"""
        return '''<h2>7-a-Side: The Middle Ground</h2>
<p>7-a-side offers a nice balance between 5-a-side intensity and 11-a-side space:</p>

<h3>Why Choose 7-a-Side?</h3>
<ul>
    <li><strong>More space</strong> - Room to play without the intensity of 5-a-side</li>
    <li><strong>Still manageable</strong> - Easier to fill than 11-a-side</li>
    <li><strong>Great for fitness</strong> - More running than 5-a-side, less than 11-a-side</li>
    <li><strong>Versatile</strong> - Can adapt to 6-a-side or 8-a-side if needed</li>
</ul>

<h3>What to Expect</h3>
<p>7-a-side games are usually played on medium-sized pitches, often at local sports centres or larger facilities. You'll need 14 players, though games can work with 12-16 players. The pace is still fast but gives you more time on the ball than 5-a-side.</p>'''
    
    def _generate_11aside_details_section(self) -> str:
        """Generate 11-a-side details section"""
        return '''<h2>11-a-Side: The Full Experience</h2>
<p>11-a-side is less common for casual games but offers the traditional football experience:</p>

<h3>Why Choose 11-a-Side?</h3>
<ul>
    <li><strong>Traditional format</strong> - The classic football experience</li>
    <li><strong>More tactical</strong> - Room for different formations and strategies</li>
    <li><strong>Great for fitness</strong> - Full-size pitch means lots of running</li>
    <li><strong>Team building</strong> - Requires more coordination and teamwork</li>
</ul>

<h3>What to Expect</h3>
<p>11-a-side games require 22 players and are usually played on full-size pitches at local sports centres or parks. Games typically last 60-90 minutes. These games are less common for casual play but you'll find some groups organising regular 11-a-side kickabouts, especially on weekends.</p>

<p>Due to the number of players needed, 11-a-side games often require more planning and commitment from organisers and players.</p>'''
    
    def _generate_which_to_choose_section(self) -> str:
        """Generate which format to choose section"""
        return '''<h2>Which Format Should You Choose?</h2>

<h3>Choose 5-a-Side If:</h3>
<ul>
    <li>You want the easiest format to organise</li>
    <li>You prefer fast-paced, intense games</li>
    <li>You're looking for after-work or quick weekend kickabouts</li>
    <li>You want maximum touches and involvement</li>
</ul>

<h3>Choose 7-a-Side If:</h3>
<ul>
    <li>You want more space than 5-a-side</li>
    <li>You can gather 12-16 players regularly</li>
    <li>You want something between casual and competitive</li>
</ul>

<h3>Choose 11-a-Side If:</h3>
<ul>
    <li>You want the traditional football experience</li>
    <li>You have a large, committed group</li>
    <li>You prefer more tactical, structured games</li>
    <li>You're organising weekend games with plenty of notice</li>
</ul>

<p><strong>For most casual players, 5-a-side is the best starting point.</strong> It's the easiest to organise, most widely available, and perfect for getting regular football into your routine.</p>'''
    
    def _generate_venues_overview_section(self, city_name: str, venues: List[str]) -> str:
        """Generate venues overview section"""
        venues_list = ", ".join(venues[:-1]) + f", and {venues[-1]}" if len(venues) > 1 else venues[0] if venues else "local facilities"
        return f'''<h2>Best Places to Play 5v5 Soccer in {city_name}</h2>
<p>{city_name} has a great selection of venues for pickup soccer, from major facilities like {venues_list} to local parks and indoor centers.</p>
<p>Whether you're looking for turf fields, indoor facilities, or local cages and parks, there's something for everyone in {city_name}.</p>'''
    
    def _generate_venue_details_section(self, venues: List[str]) -> str:
        """Generate venue details section"""
        content = "<h2>Top Venues in the Area</h2>\n"
        for venue in venues:
            content += f"<h3>{venue}</h3>\n<p>{self._venue_blurb(venue)}</p>\n"
        return content
    
    def _generate_booking_tips_section(self) -> str:
        """Generate booking tips section"""
        return '''<h2>Tips for Booking Pitches</h2>
<ul>
    <li><strong>Book in advance</strong> - Popular times (evenings, weekends) get booked up quickly</li>
    <li><strong>Check cancellation policies</strong> - Know what happens if you need to cancel</li>
    <li><strong>Consider off-peak times</strong> - Mid-week afternoons are often cheaper and easier to book</li>
    <li><strong>Ask about block bookings</strong> - Regular games can sometimes get discounts</li>
    <li><strong>Have backup venues</strong> - Keep a list of alternative options in case your first choice is booked</li>
</ul>'''
    
    def _generate_local_venues_section(self, city_name: str, venues: List[str]) -> str:
        """Generate local venues section"""
        return f'''<h2>Finding Local Venues</h2>
<p>Beyond the major facilities, {city_name} has plenty of local parks and centers that are perfect for pickup soccer. These venues often offer:</p>
<ul>
    <li>More affordable rates</li>
    <li>Community atmosphere</li>
    <li>Flexible booking</li>
    <li>Support for local football</li>
</ul>
<p>When you join {SITE_NAME}, you'll get access to our directory of venues in {city_name}, plus recommendations from other players who know the best spots.</p>'''
    
    def _generate_city_football_history_section(self, city_name: str, teams: List[str]) -> str:
        """Generate city soccer history section"""
        teams_text = ""
        if teams:
            teams_list = ", ".join(teams[:-1]) + f", and {teams[-1]}" if len(teams) > 1 else teams[0]
            teams_text = f" Home to clubs like {teams_list}, {city_name} has a strong soccer scene."
        
        return f'''<h2>Soccer Culture in {city_name}</h2>
<p>{city_name} has a passionate soccer community.{teams_text} Whether you're a fan of the local teams or just love playing, there's a vibrant soccer scene waiting for you.</p>
<p>The pickup soccer community in {city_name} is growing, with players organizing regular games across the area—from intown parks to OTP complexes and indoor turf, there are runs throughout the week.</p>'''
    
    def _generate_local_teams_section(self, teams: List[str]) -> str:
        """Generate local teams section"""
        if not teams:
            return ""
        
        content = "<h2>Local Soccer Teams</h2>\n<p>The area is home to some fantastic soccer clubs:</p>\n<ul>\n"
        for team in teams:
            content += f"<li><strong>{team}</strong> - A key part of the local soccer scene</li>\n"
        content += "</ul>\n<p>Many pickup players in the area are fans of these teams, and games often have a great atmosphere with players discussing the latest matches and results.</p>"
        return content
    
    def _generate_football_scene_section(self, city_name: str, culture: str) -> str:
        """Generate soccer scene section"""
        culture_text = culture if culture else f"The soccer scene in {city_name} is thriving"
        return f'''<h2>The Pickup Soccer Scene</h2>
<p>{culture_text}. Players are organizing games throughout the week, from after-work pickup to weekend matches.</p>

<h3>When to Play</h3>
<p>Most games happen in the evenings (6-9pm) and on weekends. These times work well for most people and you'll find plenty of options.</p>

<h3>Where to Play</h3>
<p>You'll find games at county parks, school or venue rentals, regional complexes, and indoor turf. The variety means there's something for everyone, whether you prefer grass, turf, or air-conditioned small-sided.</p>

<h3>Ability Levels</h3>
<p>Games in {city_name} cater to all abilities. You'll find beginner-friendly pickup, intermediate games, and more competitive matches. Check the game description to find the right level for you.</p>'''
    
    def _generate_joining_community_section(self, city_name: str) -> str:
        """Generate joining community section"""
        return f'''<h2>Joining the {city_name} Soccer Community</h2>
<p>The best way to get involved is to sign up to {SITE_NAME}. You'll be notified when new games go live in {city_name}, and you can browse games organized by other players.</p>

<p>Many players start by joining a few games, then go on to organize their own regular pickup. It's a great way to meet people, stay fit, and enjoy regular soccer.</p>

<p>Whether you're new to {city_name} or have been here for years, pickup soccer is a fantastic way to connect with the local community and get regular games in your routine.</p>'''
    
    def _generate_area_overview_section(self, area_name: str, city_name: str) -> str:
        """Generate area overview section"""
        return f'''<h2>Soccer in {area_name}, {city_name}</h2>
<p>{area_name} is a great area for pickup soccer, with plenty of opportunities to find or organize games. Whether you're looking for regular games or just want to join the occasional pickup, you'll find a welcoming community here.</p>

<p>The area benefits from being part of {city_name}'s wider soccer scene, with access to facilities and players across the area, while also having its own local community of players.</p>'''
    
    def _generate_finding_games_area_section(self, area_name: str, city_name: str) -> str:
        """Generate finding games in area section"""
        return f'''<h2>Finding Games in {area_name}</h2>
<p>There are several ways to find casual football games in {area_name}:</p>

<h3>1. Sign Up to {SITE_NAME}</h3>
<p>Join with your email and location ({area_name}, {city_name}), and you'll be notified when new games go live in your area. It's the easiest way to stay connected with the local soccer community.</p>

<h3>2. Check Local Venues</h3>
<p>Many venues in {area_name} have noticeboards or online listings where organizers post games. It's worth checking facilities like Chelsea Piers or local parks and indoor centers.</p>

<h3>3. Connect with Local Players</h3>
<p>Once you join a few games, you'll start meeting other players in {area_name}. Many regular games develop from these connections, so don't be shy about asking if anyone organizes regular pickup.</p>'''
    
    def _generate_organising_area_section(self, area_name: str, city_name: str) -> str:
        """Generate organising in area section"""
        return f'''<h2>Organising Games in {area_name}</h2>
<p>Want to start your own regular kickabout in {area_name}? Here's how:</p>

<h3>1. Find a Venue</h3>
<p>Look for local pitches or facilities in {area_name}. You might find venues nearby, or you could use facilities in other parts of {city_name} if they're accessible.</p>

<h3>2. Set a Regular Time</h3>
<p>Consistency helps build a regular group. Many successful games run at the same time each week. Evenings and weekends work well for most people.</p>

<h3>3. Build Your Group</h3>
<p>Start with friends or colleagues in {area_name}, then let {SITE_NAME} help you find more players. Many organizers find that word spreads quickly once they get started.</p>

<h3>4. Keep It Local</h3>
<p>Players in {area_name} often appreciate games that are nearby and easy to get to. Consider transport links and accessibility when choosing your venue.</p>'''
    
    def _generate_local_community_section(self, area_name: str, city_name: str) -> str:
        """Generate local community section"""
        return f'''<h2>The {area_name} Soccer Community</h2>
<p>The pickup soccer community in {area_name} is part of {city_name}'s wider soccer scene. You'll find players of all abilities organizing and joining games, from complete beginners to experienced players.</p>

<p>Many players appreciate the local feel of games in {area_name} - it's easier to get to, you might know some of the players, and it feels like your local soccer community.</p>

<p>Whether you're new to the area or have been here for years, joining the {area_name} soccer community is a great way to meet people, stay active, and enjoy regular pickup games.</p>'''
    
    def _generate_city_generic_content(self, post: Dict, context: Dict, city_data: Dict) -> str:
        """Generate generic city content"""
        city_name = context.get("city", "")
        return f'''{self._generate_intro_section(post, city_name)}
{self._generate_football_scene_section(city_name, city_data.get("localReferences", {}).get("culture", ""))}
{self._generate_joining_community_section(city_name)}
{self._generate_conclusion_section(post, city_name)}'''
    
    def _generate_generic_guide_content(self, post: Dict, context: Dict) -> str:
        """Generate generic guide content"""
        return f'''{self._generate_intro_section(post)}
{self._generate_what_is_section()}
{self._generate_how_to_find_section()}
{self._generate_conclusion_section(post)}'''
    
    def _generate_generic_content(self, post: Dict, context: Dict) -> str:
        """Generate generic content fallback"""
        excerpt = post.get("excerpt", "")
        return f'''<p>{excerpt}</p>
<p>Join {SITE_NAME} to find and organize pickup soccer games in your area. Sign up with your email and area to get started.</p>'''
    
    def _generate_conclusion_section(self, post: Dict, location: str = None) -> str:
        """Generate conclusion section"""
        loc = location if location is not None else HUB_MARKETING_DEFAULT
        return f'''<h2>Get Started Today</h2>
<p>Ready to find your next game in {loc}? Join {SITE_NAME} today and start connecting with players in your area.</p>

<p>Whether you're looking to join games or organise your own, we're here to help you get the most out of casual football. Sign up with your email and location, and you'll be notified when new games go live.</p>

<p>See you on the pitch!</p>'''
    
    def _get_city_data(self, city_name: str) -> Dict:
        """Get city-specific data from config"""
        for city in self.cities:
            if city.get("name") == city_name:
                return city
        return {}


def generate_blog_content(post: Dict, blog_type: str, location_context: Dict = None, sport_config: Dict = None) -> str:
    """
    Convenience function to generate blog content
    
    Args:
        post: Blog post dictionary
        blog_type: Type of blog ('country', 'city', 'area')
        location_context: Context with city, area_name, etc.
        sport_config: Sport configuration dictionary
    
    Returns:
        HTML string with blog content
    """
    if sport_config is None:
        # Try to import from generate.py context
        try:
            from generate import SPORT_CONFIG
            sport_config = SPORT_CONFIG
        except:
            sport_config = {}
    
    generator = BlogContentGenerator(sport_config)
    return generator.generate_content(post, blog_type, location_context)
