#!/usr/bin/env python3
"""
Comprehensive test script for complex UI elements with iframe and shadow DOM support.

Tests various UI patterns:
- Complex forms with validation
- Dropdown menus and navigation
- Modal dialogs and overlays
- Interactive data tables
- Custom components with shadow DOM
- Nested iframes with forms
- File uploads and rich editors
- Tab interfaces and accordions
"""

import asyncio
import tempfile
from pathlib import Path

from browser_use.browser.profile import BrowserProfile
from browser_use.browser.session import BrowserSession
from browser_use.dom.service import DOMService


async def create_complex_ui_html():
	"""Create comprehensive HTML file with complex UI elements."""
	html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Complex UI Elements Test</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: Arial, sans-serif; line-height: 1.6; margin: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .section { margin: 30px 0; padding: 20px; border: 1px solid #ddd; border-radius: 8px; }
        .section h2 { margin-bottom: 15px; color: #333; }
        
        /* Navigation Menu */
        .navbar { background: #333; padding: 0; margin-bottom: 20px; }
        .navbar ul { list-style: none; display: flex; }
        .navbar li { position: relative; }
        .navbar a { display: block; padding: 15px 20px; color: white; text-decoration: none; }
        .navbar a:hover { background: #555; }
        .dropdown { position: absolute; top: 100%; left: 0; background: #444; min-width: 200px; display: none; }
        .navbar li:hover .dropdown { display: block; }
        
        /* Forms */
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; font-weight: bold; }
        .form-group input, .form-group select, .form-group textarea { 
            width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; 
        }
        .form-row { display: flex; gap: 15px; }
        .form-row .form-group { flex: 1; }
        .btn { padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
        .btn:hover { background: #0056b3; }
        .btn-secondary { background: #6c757d; }
        .btn-danger { background: #dc3545; }
        
        /* Modal */
        .modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; 
                 background: rgba(0,0,0,0.5); }
        .modal-content { background: white; margin: 15% auto; padding: 20px; border-radius: 8px; width: 80%; max-width: 500px; }
        .close { color: #aaa; float: right; font-size: 28px; font-weight: bold; cursor: pointer; }
        .close:hover { color: black; }
        
        /* Table */
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; font-weight: bold; }
        tr:hover { background: #f5f5f5; }
        .table-actions { display: flex; gap: 5px; }
        .table-actions button { padding: 5px 10px; font-size: 12px; }
        
        /* Tabs */
        .tabs { border-bottom: 1px solid #ddd; margin-bottom: 20px; }
        .tab-button { background: none; border: none; padding: 10px 20px; cursor: pointer; border-bottom: 2px solid transparent; }
        .tab-button.active { border-bottom-color: #007bff; color: #007bff; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        
        /* Accordion */
        .accordion-item { border: 1px solid #ddd; margin-bottom: 5px; }
        .accordion-header { background: #f8f9fa; padding: 15px; cursor: pointer; user-select: none; }
        .accordion-header:hover { background: #e9ecef; }
        .accordion-content { padding: 15px; display: none; }
        .accordion-content.active { display: block; }
        
        /* Iframe container */
        .iframe-container { border: 2px solid #007bff; padding: 10px; margin: 10px 0; }
        iframe { width: 100%; height: 300px; border: 1px solid #ddd; }
        
        /* Custom dropdown */
        .custom-dropdown { position: relative; display: inline-block; }
        .custom-dropdown-button { background: white; border: 1px solid #ddd; padding: 10px 15px; cursor: pointer; min-width: 200px; text-align: left; }
        .custom-dropdown-content { position: absolute; background: white; min-width: 200px; box-shadow: 0 8px 16px rgba(0,0,0,0.2); z-index: 1; display: none; }
        .custom-dropdown-content a { color: black; padding: 12px 16px; text-decoration: none; display: block; }
        .custom-dropdown-content a:hover { background: #f1f1f1; }
        .custom-dropdown:hover .custom-dropdown-content { display: block; }
        
        /* Rich editor placeholder */
        .rich-editor { border: 1px solid #ddd; min-height: 200px; padding: 10px; }
        .editor-toolbar { background: #f8f9fa; padding: 10px; border-bottom: 1px solid #ddd; }
        .editor-toolbar button { margin-right: 5px; padding: 5px 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Complex UI Elements Test Page</h1>
        
        <!-- Navigation Menu with Dropdowns -->
        <nav class="navbar">
            <ul>
                <li><a href="#" onclick="showSection('home')">Home</a></li>
                <li>
                    <a href="#" onclick="showSection('products')">Products</a>
                    <div class="dropdown">
                        <a href="#" onclick="selectProduct('laptops')">Laptops</a>
                        <a href="#" onclick="selectProduct('phones')">Phones</a>
                        <a href="#" onclick="selectProduct('tablets')">Tablets</a>
                    </div>
                </li>
                <li>
                    <a href="#" onclick="showSection('services')">Services</a>
                    <div class="dropdown">
                        <a href="#" onclick="selectService('support')">Support</a>
                        <a href="#" onclick="selectService('consulting')">Consulting</a>
                        <a href="#" onclick="selectService('training')">Training</a>
                    </div>
                </li>
                <li><a href="#" onclick="showModal()">Contact</a></li>
            </ul>
        </nav>
        
        <!-- Complex Form Section -->
        <div class="section">
            <h2>Complex Registration Form</h2>
            <form id="registrationForm" onsubmit="submitForm(event)">
                <div class="form-row">
                    <div class="form-group">
                        <label for="firstName">First Name *</label>
                        <input type="text" id="firstName" name="firstName" required>
                    </div>
                    <div class="form-group">
                        <label for="lastName">Last Name *</label>
                        <input type="text" id="lastName" name="lastName" required>
                    </div>
                </div>
                
                <div class="form-group">
                    <label for="email">Email Address *</label>
                    <input type="email" id="email" name="email" required>
                </div>
                
                <div class="form-row">
                    <div class="form-group">
                        <label for="phone">Phone Number</label>
                        <input type="tel" id="phone" name="phone">
                    </div>
                    <div class="form-group">
                        <label for="country">Country</label>
                        <select id="country" name="country" onchange="updateStates()">
                            <option value="">Select Country</option>
                            <option value="us">United States</option>
                            <option value="ca">Canada</option>
                            <option value="uk">United Kingdom</option>
                            <option value="de">Germany</option>
                        </select>
                    </div>
                </div>
                
                <div class="form-row">
                    <div class="form-group">
                        <label for="state">State/Province</label>
                        <select id="state" name="state">
                            <option value="">Select State</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="city">City</label>
                        <input type="text" id="city" name="city">
                    </div>
                </div>
                
                <div class="form-group">
                    <label for="interests">Interests (hold Ctrl to select multiple)</label>
                    <select id="interests" name="interests" multiple size="4">
                        <option value="technology">Technology</option>
                        <option value="sports">Sports</option>
                        <option value="music">Music</option>
                        <option value="travel">Travel</option>
                        <option value="cooking">Cooking</option>
                        <option value="reading">Reading</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label for="bio">Bio/Description</label>
                    <textarea id="bio" name="bio" rows="4" placeholder="Tell us about yourself..."></textarea>
                </div>
                
                <div class="form-group">
                    <label for="profilePicture">Profile Picture</label>
                    <input type="file" id="profilePicture" name="profilePicture" accept="image/*">
                </div>
                
                <div class="form-group">
                    <label>
                        <input type="checkbox" id="newsletter" name="newsletter" value="yes">
                        Subscribe to our newsletter
                    </label>
                </div>
                
                <div class="form-group">
                    <label>Account Type:</label>
                    <label><input type="radio" name="accountType" value="personal" checked> Personal</label>
                    <label><input type="radio" name="accountType" value="business"> Business</label>
                    <label><input type="radio" name="accountType" value="enterprise"> Enterprise</label>
                </div>
                
                <div class="form-group">
                    <button type="submit" class="btn">Register</button>
                    <button type="reset" class="btn btn-secondary">Reset</button>
                    <button type="button" class="btn btn-danger" onclick="cancelForm()">Cancel</button>
                </div>
            </form>
        </div>
        
        <!-- Custom Dropdown Section -->
        <div class="section">
            <h2>Custom Dropdown Components</h2>
            <div class="custom-dropdown">
                <div class="custom-dropdown-button" onclick="toggleDropdown('dropdown1')">
                    Select Category ▼
                </div>
                <div class="custom-dropdown-content" id="dropdown1">
                    <a href="#" onclick="selectOption('electronics')">Electronics</a>
                    <a href="#" onclick="selectOption('clothing')">Clothing</a>
                    <a href="#" onclick="selectOption('books')">Books</a>
                    <a href="#" onclick="selectOption('sports')">Sports</a>
                </div>
            </div>
            
            <div class="custom-dropdown" style="margin-left: 20px;">
                <div class="custom-dropdown-button" onclick="toggleDropdown('dropdown2')">
                    Sort By ▼
                </div>
                <div class="custom-dropdown-content" id="dropdown2">
                    <a href="#" onclick="sortBy('price-low')">Price: Low to High</a>
                    <a href="#" onclick="sortBy('price-high')">Price: High to Low</a>
                    <a href="#" onclick="sortBy('newest')">Newest First</a>
                    <a href="#" onclick="sortBy('popular')">Most Popular</a>
                </div>
            </div>
        </div>
        
        <!-- Data Table Section -->
        <div class="section">
            <h2>Interactive Data Table</h2>
            <table id="dataTable">
                <thead>
                    <tr>
                        <th><input type="checkbox" onclick="selectAll(this)"></th>
                        <th onclick="sortTable(1)">Product Name ↕</th>
                        <th onclick="sortTable(2)">Price ↕</th>
                        <th onclick="sortTable(3)">Stock ↕</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><input type="checkbox" name="productSelect" value="1"></td>
                        <td>Laptop Pro</td>
                        <td>$1,299</td>
                        <td>15</td>
                        <td class="table-actions">
                            <button class="btn" onclick="editProduct(1)">Edit</button>
                            <button class="btn btn-danger" onclick="deleteProduct(1)">Delete</button>
                            <button class="btn btn-secondary" onclick="viewProduct(1)">View</button>
                        </td>
                    </tr>
                    <tr>
                        <td><input type="checkbox" name="productSelect" value="2"></td>
                        <td>Smartphone X</td>
                        <td>$899</td>
                        <td>32</td>
                        <td class="table-actions">
                            <button class="btn" onclick="editProduct(2)">Edit</button>
                            <button class="btn btn-danger" onclick="deleteProduct(2)">Delete</button>
                            <button class="btn btn-secondary" onclick="viewProduct(2)">View</button>
                        </td>
                    </tr>
                    <tr>
                        <td><input type="checkbox" name="productSelect" value="3"></td>
                        <td>Tablet Air</td>
                        <td>$649</td>
                        <td>8</td>
                        <td class="table-actions">
                            <button class="btn" onclick="editProduct(3)">Edit</button>
                            <button class="btn btn-danger" onclick="deleteProduct(3)">Delete</button>
                            <button class="btn btn-secondary" onclick="viewProduct(3)">View</button>
                        </td>
                    </tr>
                </tbody>
            </table>
            <div style="margin-top: 15px;">
                <button class="btn" onclick="addProduct()">Add New Product</button>
                <button class="btn btn-danger" onclick="deleteSelected()">Delete Selected</button>
                <button class="btn btn-secondary" onclick="exportTable()">Export CSV</button>
            </div>
        </div>
        
        <!-- Tab Interface Section -->
        <div class="section">
            <h2>Tab Interface</h2>
            <div class="tabs">
                <button class="tab-button active" onclick="showTab('tab1')">Dashboard</button>
                <button class="tab-button" onclick="showTab('tab2')">Analytics</button>
                <button class="tab-button" onclick="showTab('tab3')">Settings</button>
                <button class="tab-button" onclick="showTab('tab4')">Help</button>
            </div>
            
            <div id="tab1" class="tab-content active">
                <h3>Dashboard Content</h3>
                <p>This is the dashboard with key metrics and quick actions.</p>
                <button class="btn" onclick="refreshDashboard()">Refresh Data</button>
                <button class="btn btn-secondary" onclick="exportDashboard()">Export Report</button>
            </div>
            
            <div id="tab2" class="tab-content">
                <h3>Analytics Content</h3>
                <p>Detailed analytics and reporting tools.</p>
                <select onchange="changeTimeframe(this.value)">
                    <option value="7d">Last 7 days</option>
                    <option value="30d">Last 30 days</option>
                    <option value="90d">Last 90 days</option>
                    <option value="1y">Last year</option>
                </select>
                <button class="btn" onclick="generateReport()">Generate Report</button>
            </div>
            
            <div id="tab3" class="tab-content">
                <h3>Settings Content</h3>
                <p>Application settings and preferences.</p>
                <label><input type="checkbox"> Enable notifications</label><br>
                <label><input type="checkbox"> Auto-save changes</label><br>
                <label><input type="checkbox"> Dark mode</label><br>
                <button class="btn" onclick="saveSettings()">Save Settings</button>
            </div>
            
            <div id="tab4" class="tab-content">
                <h3>Help Content</h3>
                <p>Documentation and support resources.</p>
                <button class="btn" onclick="openHelp()">Open Help Center</button>
                <button class="btn btn-secondary" onclick="contactSupport()">Contact Support</button>
            </div>
        </div>
        
        <!-- Accordion Section -->
        <div class="section">
            <h2>Accordion Interface</h2>
            <div class="accordion-item">
                <div class="accordion-header" onclick="toggleAccordion('acc1')">
                    FAQ: What is your return policy? ▼
                </div>
                <div class="accordion-content" id="acc1">
                    <p>Our return policy allows returns within 30 days of purchase with original receipt.</p>
                    <button class="btn btn-secondary" onclick="readMore('returns')">Read Full Policy</button>
                </div>
            </div>
            
            <div class="accordion-item">
                <div class="accordion-header" onclick="toggleAccordion('acc2')">
                    FAQ: How do I track my order? ▼
                </div>
                <div class="accordion-content" id="acc2">
                    <p>You can track your order using the tracking number sent to your email.</p>
                    <input type="text" placeholder="Enter tracking number" style="margin: 10px 0;">
                    <button class="btn" onclick="trackOrder()">Track Order</button>
                </div>
            </div>
            
            <div class="accordion-item">
                <div class="accordion-header" onclick="toggleAccordion('acc3')">
                    FAQ: What payment methods do you accept? ▼
                </div>
                <div class="accordion-content" id="acc3">
                    <p>We accept all major credit cards, PayPal, and bank transfers.</p>
                    <div>
                        <label><input type="checkbox"> Credit Card</label>
                        <label><input type="checkbox"> PayPal</label>
                        <label><input type="checkbox"> Bank Transfer</label>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Rich Editor Section -->
        <div class="section">
            <h2>Rich Text Editor</h2>
            <div class="rich-editor">
                <div class="editor-toolbar">
                    <button onclick="formatText('bold')"><b>B</b></button>
                    <button onclick="formatText('italic')"><i>I</i></button>
                    <button onclick="formatText('underline')"><u>U</u></button>
                    <button onclick="insertLink()">Link</button>
                    <button onclick="insertImage()">Image</button>
                    <select onchange="changeFontSize(this.value)">
                        <option value="12">12px</option>
                        <option value="14" selected>14px</option>
                        <option value="16">16px</option>
                        <option value="18">18px</option>
                    </select>
                    <button onclick="alignText('left')">Left</button>
                    <button onclick="alignText('center')">Center</button>
                    <button onclick="alignText('right')">Right</button>
                </div>
                <div contenteditable="true" style="padding: 15px; min-height: 150px;" 
                     placeholder="Start typing your content here...">
                    Click here to start editing content...
                </div>
            </div>
            <div style="margin-top: 10px;">
                <button class="btn" onclick="saveContent()">Save Content</button>
                <button class="btn btn-secondary" onclick="previewContent()">Preview</button>
                <button class="btn btn-danger" onclick="clearContent()">Clear All</button>
            </div>
        </div>
        
        <!-- Iframe Section -->
        <div class="section">
            <h2>Embedded Iframe Content</h2>
            <div class="iframe-container">
                <h3>External Payment Form (Iframe)</h3>
                <iframe src="data:text/html,
                    <html>
                    <head><title>Payment Form</title></head>
                    <body style='font-family: Arial; padding: 20px;'>
                        <h3>Secure Payment</h3>
                        <form>
                            <div style='margin: 10px 0;'>
                                <label>Card Number:</label><br>
                                <input type='text' placeholder='1234 5678 9012 3456' style='width: 100%; padding: 8px;'>
                            </div>
                            <div style='display: flex; gap: 10px;'>
                                <div style='flex: 1;'>
                                    <label>Expiry:</label><br>
                                    <input type='text' placeholder='MM/YY' style='width: 100%; padding: 8px;'>
                                </div>
                                <div style='flex: 1;'>
                                    <label>CVV:</label><br>
                                    <input type='text' placeholder='123' style='width: 100%; padding: 8px;'>
                                </div>
                            </div>
                            <div style='margin: 15px 0;'>
                                <button type='submit' style='background: #28a745; color: white; padding: 10px 20px; border: none; border-radius: 4px;'>
                                    Pay Now
                                </button>
                                <button type='button' style='background: #6c757d; color: white; padding: 10px 20px; border: none; border-radius: 4px; margin-left: 10px;'>
                                    Cancel
                                </button>
                            </div>
                        </form>
                    </body>
                    </html>
                " style="width: 100%; height: 200px;"></iframe>
            </div>
            
            <div class="iframe-container">
                <h3>Support Chat Widget (Iframe)</h3>
                <iframe src="data:text/html,
                    <html>
                    <body style='font-family: Arial; padding: 15px; background: #f8f9fa;'>
                        <div style='background: white; border-radius: 8px; padding: 15px;'>
                            <h4>Chat with Support</h4>
                            <div style='height: 100px; overflow-y: auto; background: #f1f1f1; padding: 10px; margin: 10px 0; border-radius: 4px;'>
                                <div><strong>Support:</strong> How can we help you today?</div>
                            </div>
                            <div style='display: flex; gap: 10px;'>
                                <input type='text' placeholder='Type your message...' style='flex: 1; padding: 8px; border: 1px solid #ddd; border-radius: 4px;'>
                                <button style='background: #007bff; color: white; border: none; padding: 8px 15px; border-radius: 4px;'>Send</button>
                            </div>
                            <div style='margin-top: 10px;'>
                                <button style='background: #28a745; color: white; border: none; padding: 5px 10px; border-radius: 4px; margin-right: 5px;'>Start Video Call</button>
                                <button style='background: #ffc107; color: black; border: none; padding: 5px 10px; border-radius: 4px;'>Request Callback</button>
                            </div>
                        </div>
                    </body>
                    </html>
                " style="width: 100%; height: 180px;"></iframe>
            </div>
        </div>
    </div>
    
    <!-- Modal Dialog -->
    <div id="contactModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal()">&times;</span>
            <h3>Contact Us</h3>
            <form id="contactForm">
                <div class="form-group">
                    <label for="contactName">Name:</label>
                    <input type="text" id="contactName" name="contactName" required>
                </div>
                <div class="form-group">
                    <label for="contactEmail">Email:</label>
                    <input type="email" id="contactEmail" name="contactEmail" required>
                </div>
                <div class="form-group">
                    <label for="contactSubject">Subject:</label>
                    <select id="contactSubject" name="contactSubject">
                        <option value="general">General Inquiry</option>
                        <option value="support">Technical Support</option>
                        <option value="sales">Sales Question</option>
                        <option value="feedback">Feedback</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="contactMessage">Message:</label>
                    <textarea id="contactMessage" name="contactMessage" rows="4" required></textarea>
                </div>
                <div class="form-group">
                    <button type="submit" class="btn">Send Message</button>
                    <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                </div>
            </form>
        </div>
    </div>

    <script>
        // JavaScript functions for interactivity
        function showSection(section) {
            console.log('Showing section:', section);
        }
        
        function selectProduct(product) {
            console.log('Selected product:', product);
        }
        
        function selectService(service) {
            console.log('Selected service:', service);
        }
        
        function showModal() {
            document.getElementById('contactModal').style.display = 'block';
        }
        
        function closeModal() {
            document.getElementById('contactModal').style.display = 'none';
        }
        
        function submitForm(event) {
            event.preventDefault();
            console.log('Form submitted');
            alert('Registration form submitted!');
        }
        
        function updateStates() {
            const country = document.getElementById('country').value;
            const stateSelect = document.getElementById('state');
            stateSelect.innerHTML = '<option value="">Select State</option>';
            
            if (country === 'us') {
                stateSelect.innerHTML += '<option value="ca">California</option><option value="ny">New York</option><option value="tx">Texas</option>';
            } else if (country === 'ca') {
                stateSelect.innerHTML += '<option value="on">Ontario</option><option value="bc">British Columbia</option>';
            }
        }
        
        function toggleDropdown(id) {
            const dropdown = document.getElementById(id);
            dropdown.style.display = dropdown.style.display === 'block' ? 'none' : 'block';
        }
        
        function selectOption(option) {
            console.log('Selected option:', option);
        }
        
        function sortBy(criteria) {
            console.log('Sort by:', criteria);
        }
        
        function selectAll(checkbox) {
            const checkboxes = document.querySelectorAll('input[name="productSelect"]');
            checkboxes.forEach(cb => cb.checked = checkbox.checked);
        }
        
        function sortTable(column) {
            console.log('Sort table by column:', column);
        }
        
        function editProduct(id) {
            console.log('Edit product:', id);
        }
        
        function deleteProduct(id) {
            if (confirm('Are you sure you want to delete this product?')) {
                console.log('Delete product:', id);
            }
        }
        
        function viewProduct(id) {
            console.log('View product:', id);
        }
        
        function showTab(tabId) {
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
            
            // Show selected tab
            document.getElementById(tabId).classList.add('active');
            event.target.classList.add('active');
        }
        
        function toggleAccordion(id) {
            const content = document.getElementById(id);
            content.classList.toggle('active');
        }
        
        function formatText(format) {
            document.execCommand(format, false, null);
        }
        
        function insertLink() {
            const url = prompt('Enter URL:');
            if (url) {
                document.execCommand('createLink', false, url);
            }
        }
        
        // Add more interactive functions as needed
        function cancelForm() { console.log('Form cancelled'); }
        function addProduct() { console.log('Add new product'); }
        function deleteSelected() { console.log('Delete selected products'); }
        function exportTable() { console.log('Export table to CSV'); }
        function refreshDashboard() { console.log('Refresh dashboard'); }
        function exportDashboard() { console.log('Export dashboard'); }
        function changeTimeframe(value) { console.log('Change timeframe:', value); }
        function generateReport() { console.log('Generate report'); }
        function saveSettings() { console.log('Save settings'); }
        function openHelp() { console.log('Open help center'); }
        function contactSupport() { console.log('Contact support'); }
        function readMore(topic) { console.log('Read more about:', topic); }
        function trackOrder() { console.log('Track order'); }
        function insertImage() { console.log('Insert image'); }
        function changeFontSize(size) { console.log('Change font size:', size); }
        function alignText(alignment) { console.log('Align text:', alignment); }
        function saveContent() { console.log('Save content'); }
        function previewContent() { console.log('Preview content'); }
        function clearContent() { console.log('Clear content'); }
        
        // Close modal when clicking outside
        window.onclick = function(event) {
            const modal = document.getElementById('contactModal');
            if (event.target === modal) {
                modal.style.display = 'none';
            }
        }
    </script>
</body>
</html>
    """

	# Create temporary HTML file
	temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8')
	temp_file.write(html_content)
	temp_file.close()

	return Path(temp_file.name).as_uri()


async def test_complex_ui_extraction():
	"""Test DOM extraction on complex UI elements."""

	# Create browser session
	profile = BrowserProfile(headless=False, keep_alive=True)
	browser_session = BrowserSession(browser_profile=profile)

	try:
		await browser_session.start()

		# Create and navigate to complex UI test page
		test_url = await create_complex_ui_html()
		print(f'🌐 Created test page: {test_url}')

		await browser_session.navigate_to(test_url)
		await asyncio.sleep(3)  # Wait for page to load completely

		# Create DOM service
		dom_service = DOMService(browser_session)

		print('\n' + '=' * 80)
		print('🧪 COMPLEX UI ELEMENTS EXTRACTION TEST')
		print('=' * 80)

		# Test different filter modes
		filter_modes = ['comprehensive', 'balanced', 'minimal']

		for mode in filter_modes:
			print(f'\n🔍 Testing filter mode: {mode}')
			print('-' * 50)

			serialized, selector_map = await dom_service.get_serialized_dom_tree(filter_mode=mode)

			print(f'📊 Found {len(selector_map)} interactive elements')

			# Analyze element types
			element_types = {}
			context_counts = {'main': 0, 'iframe': 0, 'shadow': 0}

			for idx, node in selector_map.items():
				tag_name = node.node_name.upper()
				element_types[tag_name] = element_types.get(tag_name, 0) + 1

				# Check context (iframe/shadow)
				if 'iframe' in str(node.x_path or '').lower():
					context_counts['iframe'] += 1
				elif 'shadow' in str(node.x_path or '').lower():
					context_counts['shadow'] += 1
				else:
					context_counts['main'] += 1

			print('📋 Element types detected:')
			for tag, count in sorted(element_types.items()):
				print(f'  - {tag}: {count}')

			print('🌍 Context distribution:')
			print(f'  - Main document: {context_counts["main"]}')
			print(f'  - Iframe content: {context_counts["iframe"]}')
			print(f'  - Shadow DOM: {context_counts["shadow"]}')

			# Sample some complex elements
			print('\n🎯 Sample interactive elements:')
			sample_count = min(10, len(selector_map))
			for i, (idx, node) in enumerate(list(selector_map.items())[:sample_count]):
				tag = node.node_name.upper()
				attrs = []
				if node.attributes:
					if 'id' in node.attributes:
						attrs.append(f'id="{node.attributes["id"]}"')
					if 'type' in node.attributes:
						attrs.append(f'type="{node.attributes["type"]}"')
					if 'onclick' in node.attributes:
						attrs.append('onclick="..."')

				attr_str = ' '.join(attrs)
				print(f'  [{idx}] <{tag}{" " + attr_str if attr_str else ""}>')

			# Show partial serialized output
			if len(serialized) > 1000:
				print('\n📄 Serialized output (first 800 chars):')
				print(serialized[:800] + '...\n[TRUNCATED]')
			else:
				print('\n📄 Complete serialized output:')
				print(serialized)

			print(f'\n✅ Filter mode "{mode}" test completed')

		print('\n' + '=' * 80)
		print('🎯 IFRAME CONTENT VERIFICATION')
		print('=' * 80)

		# Test iframe content extraction specifically
		serialized, selector_map = await dom_service.get_serialized_dom_tree(filter_mode='comprehensive')

		# Look for iframe-specific elements
		iframe_elements = []
		payment_elements = []
		chat_elements = []

		for idx, node in selector_map.items():
			if node.attributes:
				# Check for payment form elements
				if (
					node.attributes.get('placeholder', '').find('1234') != -1
					or node.attributes.get('placeholder', '').find('MM/YY') != -1
					or node.attributes.get('placeholder', '').find('CVV') != -1
				):
					payment_elements.append((idx, node))

				# Check for chat elements
				if (
					node.attributes.get('placeholder', '').find('message') != -1
					or 'Send' in str(node.node_value or '')
					or 'Video Call' in str(node.node_value or '')
				):
					chat_elements.append((idx, node))

		print(f'💳 Payment form elements detected: {len(payment_elements)}')
		for idx, node in payment_elements:
			placeholder = node.attributes.get('placeholder', '') if node.attributes else ''
			print(f'  [{idx}] {node.node_name.upper()} placeholder="{placeholder}"')

		print(f'💬 Chat widget elements detected: {len(chat_elements)}')
		for idx, node in chat_elements:
			value = str(node.node_value or '')[:50] if node.node_value else ''
			print(f'  [{idx}] {node.node_name.upper()} value="{value}"')

		# Test form interaction detection
		print('\n📝 FORM INTERACTION ANALYSIS')
		print('-' * 50)

		form_elements = {}
		for idx, node in selector_map.items():
			tag = node.node_name.upper()
			if tag in ['INPUT', 'SELECT', 'TEXTAREA', 'BUTTON']:
				input_type = node.attributes.get('type', 'text') if node.attributes else 'text'
				form_key = f'{tag}({input_type})'
				form_elements[form_key] = form_elements.get(form_key, 0) + 1

		print('📊 Form elements by type:')
		for form_type, count in sorted(form_elements.items()):
			print(f'  - {form_type}: {count}')

		print('\n🎉 Complex UI extraction test completed successfully!')
		print(f'📊 Total interactive elements found: {len(selector_map)}')

		# Wait a bit for user to see the results
		await asyncio.sleep(2)

	except Exception as e:
		print(f'❌ Error during complex UI test: {e}')
		import traceback

		traceback.print_exc()
	finally:
		await browser_session.stop()


if __name__ == '__main__':
	asyncio.run(test_complex_ui_extraction())
