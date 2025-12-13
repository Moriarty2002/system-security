/**
 * System Use Notification Banner
 * Implements AC-8 compliance for NIST 800-53 Rev 5
 * 
 * Displays a mandatory system use notification that users must
 * acknowledge before accessing the system.
 */

const SystemBanner = {
  shown: false,
  
  getBannerHTML() {
    return `
      <div id="systemBannerOverlay" class="banner-overlay" role="dialog" aria-labelledby="bannerTitle" aria-modal="true">
        <div class="banner-modal">
          <div class="banner-header">
            <h2 id="bannerTitle">⚠️ SYSTEM USE NOTIFICATION</h2>
          </div>
          
          <div class="banner-body">
            <section>
              <h3>AUTHORIZED USE ONLY</h3>
              <p>This system is restricted to authorized users only. Individuals attempting unauthorized access will be prosecuted. If you are not an authorized user, you must exit immediately.</p>
            </section>
            
            <section>
              <h3>MONITORING AND RECORDING</h3>
              <p>Use of this system constitutes consent to monitoring, interception, recording, reading, copying, or capturing by authorized personnel of all activities. There is no right to privacy in this system. Unauthorized or improper use may result in administrative disciplinary action, civil charges, or criminal penalties.</p>
            </section>
            
            <section>
              <h3>NO EXPECTATION OF PRIVACY</h3>
              <p>By proceeding, you acknowledge that you have no expectation of privacy with respect to any communications or data processed, transmitted, or stored on this system. All information may be disclosed to authorized personnel for official purposes.</p>
            </section>
            
            <section>
              <h3>ACCEPTABLE USE</h3>
              <p>You must comply with all organizational policies and applicable laws governing the use of this system. Violations may result in disciplinary action, termination of access privileges, and/or criminal prosecution.</p>
            </section>
            
            <section>
              <h3>AUDIT AND COMPLIANCE</h3>
              <p>All actions performed on this system are logged and audited. By using this system, you consent to such auditing and agree that audit logs may be used as evidence in legal or administrative proceedings.</p>
            </section>
          </div>
          
          <div class="banner-footer">
            <label class="banner-checkbox">
              <input type="checkbox" id="bannerAcknowledge" required aria-required="true">
              <span>I acknowledge that I have read and understand this notice and agree to comply with all applicable policies and regulations.</span>
            </label>
            
            <div class="banner-actions">
              <button id="bannerAccept" class="btn btn-primary" disabled aria-disabled="true">
                ✓ Accept and Continue
              </button>
              <button id="bannerDecline" class="btn btn-secondary">
                ✗ Decline and Exit
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  },
  
  show() {
    if (this.shown) return;
    
    // Check if user has already acknowledged in this session
    const acknowledged = sessionStorage.getItem('bannerAcknowledged');
    const acknowledgedTime = sessionStorage.getItem('bannerAcknowledgedAt');
    
    if (acknowledged === 'true' && acknowledgedTime) {
      // Check if acknowledgment is still valid (within same session)
      const ackTime = new Date(acknowledgedTime);
      const now = new Date();
      const hoursSinceAck = (now - ackTime) / (1000 * 60 * 60);
      
      // Require re-acknowledgment after 8 hours
      if (hoursSinceAck < 8) {
        console.log('Banner already acknowledged in this session');
        return;
      }
    }
    
    // Insert banner HTML
    document.body.insertAdjacentHTML('beforeend', this.getBannerHTML());
    
    // Prevent body scrolling while banner is displayed
    document.body.style.overflow = 'hidden';
    
    // Setup event listeners
    const checkbox = document.getElementById('bannerAcknowledge');
    const acceptBtn = document.getElementById('bannerAccept');
    const declineBtn = document.getElementById('bannerDecline');
    
    checkbox.addEventListener('change', () => {
      acceptBtn.disabled = !checkbox.checked;
      acceptBtn.setAttribute('aria-disabled', !checkbox.checked);
    });
    
    acceptBtn.addEventListener('click', () => {
      this.accept();
    });
    
    declineBtn.addEventListener('click', () => {
      this.decline();
    });
    
    // Focus on checkbox for accessibility
    setTimeout(() => {
      checkbox.focus();
    }, 100);
    
    this.shown = true;
  },
  
  accept() {
    const timestamp = new Date().toISOString();
    const ipAddress = 'client'; // Will be logged server-side
    
    // Store acknowledgment in session storage
    sessionStorage.setItem('bannerAcknowledged', 'true');
    sessionStorage.setItem('bannerAcknowledgedAt', timestamp);
    
    // Log acknowledgment to backend
    this.logAcknowledgment(timestamp, ipAddress);
    
    // Remove banner and restore scrolling
    const overlay = document.getElementById('systemBannerOverlay');
    if (overlay) {
      overlay.remove();
    }
    document.body.style.overflow = '';
    
    console.log('System use banner acknowledged at:', timestamp);
  },
  
  decline() {
    // Clear any stored acknowledgment
    sessionStorage.removeItem('bannerAcknowledged');
    sessionStorage.removeItem('bannerAcknowledgedAt');
    
    // Show warning
    alert('You must acknowledge the system use notification to access this system. The page will now close.');
    
    // Redirect to blank page or close
    window.location.href = 'about:blank';
  },
  
  async logAcknowledgment(timestamp, ipAddress) {
    try {
      const response = await fetch('/api/banner/acknowledge', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          timestamp: timestamp,
          userAgent: navigator.userAgent,
          acknowledged: true
        })
      });
      
      if (!response.ok) {
        console.warn('Failed to log banner acknowledgment to backend');
      }
    } catch (error) {
      // Non-critical error - user can still proceed
      console.error('Error logging banner acknowledgment:', error);
    }
  }
};

// Auto-show banner on page load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    SystemBanner.show();
  });
} else {
  // DOM already loaded
  SystemBanner.show();
}
