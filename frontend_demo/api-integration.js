/**
 * @file API Integration Example for Browser Profile Management
 * 
 * This file demonstrates how to integrate the copy UUID functionality
 * with the browser-use cloud backend API to fetch and display profile IDs.
 * 
 * @author Browser Use Cloud Team
 * @purpose Provides backend integration for profile ID management
 */

// API Configuration
const API_CONFIG = {
    baseUrl: process.env.BROWSER_USE_BASE_URL || 'https://api.browser-use.com/api/v1',
    timeout: 30000,
    headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${process.env.BROWSER_USE_API_KEY}`
    }
};

/**
 * Browser Profile API Service
 * Handles all API interactions for browser profile management
 */
class BrowserProfileAPI {
    constructor(config = API_CONFIG) {
        this.config = config;
    }

    /**
     * Fetch all browser profiles for the current user
     * @returns {Promise<BrowserProfile[]>} Array of browser profiles
     */
    async getProfiles() {
        try {
            const response = await fetch(`${this.config.baseUrl}/profiles`, {
                method: 'GET',
                headers: this.config.headers,
                signal: AbortSignal.timeout(this.config.timeout)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            return data.profiles || [];
        } catch (error) {
            console.error('Failed to fetch profiles:', error);
            throw error;
        }
    }

    /**
     * Get a specific browser profile by ID
     * @param {string} profileId - The UUID of the profile
     * @returns {Promise<BrowserProfile>} The browser profile
     */
    async getProfile(profileId) {
        try {
            const response = await fetch(`${this.config.baseUrl}/profiles/${profileId}`, {
                method: 'GET',
                headers: this.config.headers,
                signal: AbortSignal.timeout(this.config.timeout)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`Failed to fetch profile ${profileId}:`, error);
            throw error;
        }
    }

    /**
     * Update a browser profile
     * @param {string} profileId - The UUID of the profile
     * @param {Partial<BrowserProfile>} updates - The profile updates
     * @returns {Promise<BrowserProfile>} The updated profile
     */
    async updateProfile(profileId, updates) {
        try {
            const response = await fetch(`${this.config.baseUrl}/profiles/${profileId}`, {
                method: 'PATCH',
                headers: this.config.headers,
                body: JSON.stringify(updates),
                signal: AbortSignal.timeout(this.config.timeout)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`Failed to update profile ${profileId}:`, error);
            throw error;
        }
    }

    /**
     * Delete a browser profile
     * @param {string} profileId - The UUID of the profile
     * @returns {Promise<void>}
     */
    async deleteProfile(profileId) {
        try {
            const response = await fetch(`${this.config.baseUrl}/profiles/${profileId}`, {
                method: 'DELETE',
                headers: this.config.headers,
                signal: AbortSignal.timeout(this.config.timeout)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
        } catch (error) {
            console.error(`Failed to delete profile ${profileId}:`, error);
            throw error;
        }
    }
}

/**
 * Profile Manager - Handles UI interactions with profiles
 */
class ProfileManager {
    constructor() {
        this.api = new BrowserProfileAPI();
        this.profiles = [];
        this.currentProfile = null;
    }

    /**
     * Initialize the profile manager
     */
    async init() {
        try {
            await this.loadProfiles();
            this.renderProfiles();
            this.setupEventListeners();
        } catch (error) {
            console.error('Failed to initialize profile manager:', error);
            this.showError('Failed to load profiles. Please refresh the page.');
        }
    }

    /**
     * Load profiles from the API
     */
    async loadProfiles() {
        this.profiles = await this.api.getProfiles();
    }

    /**
     * Render profiles in the UI
     */
    renderProfiles() {
        const container = document.getElementById('profiles-container');
        if (!container) return;

        container.innerHTML = this.profiles.map(profile => 
            this.renderProfileCard(profile)
        ).join('');
    }

    /**
     * Render a single profile card
     * @param {BrowserProfile} profile - The profile to render
     * @returns {string} HTML string for the profile card
     */
    renderProfileCard(profile) {
        return `
            <div class="profile-card" data-profile-id="${profile.id}">
                <div class="profile-header">
                    <div class="profile-name">${this.escapeHtml(profile.name || 'Unnamed Profile')}</div>
                    <div class="profile-actions">
                        <button class="btn btn-copy" onclick="profileManager.copyProfileId('${profile.id}')" title="Copy Profile ID">
                            <svg class="icon" viewBox="0 0 24 24">
                                <path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>
                            </svg>
                            <div class="copy-tooltip">Copied!</div>
                        </button>
                        <button class="btn" onclick="profileManager.editProfile('${profile.id}')" title="Edit Profile">
                            <svg class="icon" viewBox="0 0 24 24">
                                <path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/>
                            </svg>
                        </button>
                        <button class="btn btn-delete" onclick="profileManager.deleteProfile('${profile.id}')" title="Delete Profile">
                            <svg class="icon" viewBox="0 0 24 24">
                                <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
                            </svg>
                        </button>
                    </div>
                </div>
                <div class="profile-description">${this.escapeHtml(profile.description || '')}</div>
                <div class="profile-meta">
                    ${profile.viewport ? `<span>📱 Viewport ${profile.viewport.width} × ${profile.viewport.height}</span>` : ''}
                    ${profile.enable_default_extensions ? `<span>🛡️ Ad Blocker</span>` : ''}
                    ${profile.is_mobile ? `<span>📱 Mobile</span>` : ''}
                    ${profile.proxy ? `<span>🌐 Proxy</span>` : ''}
                </div>
            </div>
        `;
    }

    /**
     * Copy profile ID to clipboard
     * @param {string} profileId - The profile ID to copy
     */
    async copyProfileId(profileId) {
        try {
            await navigator.clipboard.writeText(profileId);
            
            // Show success feedback
            const button = document.querySelector(`[data-profile-id="${profileId}"] .btn-copy`);
            if (button) {
                const tooltip = button.querySelector('.copy-tooltip');
                tooltip.classList.add('show');
                setTimeout(() => {
                    tooltip.classList.remove('show');
                }, 2000);
            }

            // Optional: Analytics tracking
            this.trackEvent('profile_id_copied', { profileId });
        } catch (error) {
            console.error('Failed to copy profile ID:', error);
            this.showError('Failed to copy profile ID to clipboard');
        }
    }

    /**
     * Edit a profile
     * @param {string} profileId - The profile ID to edit
     */
    async editProfile(profileId) {
        try {
            const profile = await this.api.getProfile(profileId);
            this.currentProfile = profile;
            this.showEditModal(profile);
        } catch (error) {
            console.error('Failed to load profile for editing:', error);
            this.showError('Failed to load profile details');
        }
    }

    /**
     * Show the edit modal with profile data
     * @param {BrowserProfile} profile - The profile to edit
     */
    showEditModal(profile) {
        const modal = document.getElementById('editModal');
        const profileIdElement = document.getElementById('modalProfileId');
        const profileNameElement = document.getElementById('profileName');
        const profileDescriptionElement = document.getElementById('profileDescription');
        const viewportWidthElement = document.getElementById('viewportWidth');
        const viewportHeightElement = document.getElementById('viewportHeight');

        // Populate modal with profile data
        if (profileIdElement) profileIdElement.textContent = profile.id;
        if (profileNameElement) profileNameElement.value = profile.name || '';
        if (profileDescriptionElement) profileDescriptionElement.value = profile.description || '';
        if (viewportWidthElement) viewportWidthElement.value = profile.viewport?.width || 1280;
        if (viewportHeightElement) viewportHeightElement.value = profile.viewport?.height || 960;

        // Set toggle states
        this.setToggleState('persist-data', profile.user_data_dir !== null);
        this.setToggleState('store-cache', profile.enable_default_extensions);
        this.setToggleState('mobile-browser', profile.is_mobile);
        this.setToggleState('ad-blocker', profile.enable_default_extensions);
        this.setToggleState('use-proxy', profile.proxy !== null);

        modal.classList.add('active');
    }

    /**
     * Set the state of a toggle switch
     * @param {string} toggleId - The ID of the toggle
     * @param {boolean} active - Whether the toggle should be active
     */
    setToggleState(toggleId, active) {
        const toggle = document.querySelector(`[data-toggle-id="${toggleId}"]`);
        if (toggle) {
            if (active) {
                toggle.classList.add('active');
            } else {
                toggle.classList.remove('active');
            }
        }
    }

    /**
     * Delete a profile
     * @param {string} profileId - The profile ID to delete
     */
    async deleteProfile(profileId) {
        if (!confirm('Are you sure you want to delete this profile? This action cannot be undone.')) {
            return;
        }

        try {
            await this.api.deleteProfile(profileId);
            await this.loadProfiles();
            this.renderProfiles();
            this.showSuccess('Profile deleted successfully');
        } catch (error) {
            console.error('Failed to delete profile:', error);
            this.showError('Failed to delete profile');
        }
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Close modal when clicking outside
        const modal = document.getElementById('editModal');
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.closeModal();
                }
            });
        }

        // Close modal with Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeModal();
            }
        });
    }

    /**
     * Close the edit modal
     */
    closeModal() {
        const modal = document.getElementById('editModal');
        if (modal) {
            modal.classList.remove('active');
        }
        this.currentProfile = null;
    }

    /**
     * Show an error message
     * @param {string} message - The error message
     */
    showError(message) {
        // Implementation depends on your notification system
        console.error(message);
        alert(message); // Replace with your notification system
    }

    /**
     * Show a success message
     * @param {string} message - The success message
     */
    showSuccess(message) {
        // Implementation depends on your notification system
        console.log(message);
    }

    /**
     * Track analytics events
     * @param {string} event - The event name
     * @param {object} data - The event data
     */
    trackEvent(event, data) {
        // Implementation depends on your analytics system
        console.log('Analytics:', event, data);
    }

    /**
     * Escape HTML to prevent XSS
     * @param {string} text - The text to escape
     * @returns {string} The escaped text
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Type definitions for TypeScript users
/**
 * @typedef {Object} ViewportSize
 * @property {number} width - The viewport width
 * @property {number} height - The viewport height
 */

/**
 * @typedef {Object} ProxySettings
 * @property {string} server - The proxy server URL
 * @property {string} [username] - The proxy username
 * @property {string} [password] - The proxy password
 * @property {string[]} [bypass] - URLs to bypass proxy
 */

/**
 * @typedef {Object} BrowserProfile
 * @property {string} id - The unique profile ID (UUID)
 * @property {string} name - The profile name
 * @property {string} [description] - The profile description
 * @property {ViewportSize} [viewport] - The viewport size
 * @property {boolean} [is_mobile] - Whether this is a mobile profile
 * @property {boolean} [enable_default_extensions] - Whether to enable ad blocking
 * @property {string} [user_data_dir] - The user data directory path
 * @property {ProxySettings} [proxy] - The proxy settings
 * @property {string} created_at - The creation timestamp
 * @property {string} updated_at - The last update timestamp
 */

// Initialize the profile manager when the DOM is ready
if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', () => {
        window.profileManager = new ProfileManager();
        window.profileManager.init();
    });
}

// Export for Node.js environments
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        BrowserProfileAPI,
        ProfileManager,
        API_CONFIG
    };
}