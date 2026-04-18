/**
 * Tutorial Assistant JS
 * Handles the flying robot tutorial for first-time users.
 */

(function() {
    // Configuration for tutorial steps
    const steps = [
        {
            id: 'nav-logo',
            text: "Hello! I'm your Gateway Assistant. Welcome to the platform! Click the logo anytime to return to this dashboard.",
            position: 'bottom-right'
        },
        {
            id: 'search-section',
            text: "Searching for something specific? Use this bar to find investors, startups, or specific categories.",
            position: 'bottom'
        },
        {
            id: 'profile-btn',
            text: "Don't forget to complete your profile! A complete profile increases your trust score and visibility.",
            position: 'bottom'
        },
        {
            id: 'ideas-btn',
            text: "Have a breakthrough idea? Submit it here to get analyzed by our neural engine and shared with investors.",
            position: 'bottom'
        },
        {
            id: 'notifications-btn',
            text: "Stay updated! Check here for alerts about your idea's verification status or investor interest.",
            position: 'bottom-left'
        },
        {
            id: 'messages-btn',
            text: "Connect directly! Use the messaging center to talk with strategic partners and founders.",
            position: 'bottom-left'
        }
    ];

    let currentStep = 0;
    let robotEl = null;
    let bubbleEl = null;

    function createRobot() {
        if (robotEl) return;

        // Container
        robotEl = document.createElement('div');
        robotEl.id = 'tutorial-robot';
        robotEl.innerHTML = `
            <img src="/static/project_review/images/robot.png" alt="Robot assistant" />
            <div id="tutorial-bubble">
                <p id="tutorial-text"></p>
                <div class="tutorial-actions">
                    <button id="tutorial-skip">Skip</button>
                    <button id="tutorial-next">Next</button>
                </div>
            </div>
        `;
        document.body.appendChild(robotEl);

        bubbleEl = document.getElementById('tutorial-bubble');
        
        // Add Styles
        const style = document.createElement('style');
        style.textContent = `
            #tutorial-robot {
                position: fixed;
                width: 150px;
                height: 150px;
                z-index: 10000;
                transition: all 1.2s cubic-bezier(0.19, 1, 0.22, 1);
                pointer-events: none;
                filter: drop-shadow(0 15px 30px rgba(0,0,0,0.3));
            }
            #tutorial-robot img {
                width: 100%;
                height: 100%;
                object-fit: contain;
                animation: robotWave 4s ease-in-out infinite;
                pointer-events: auto;
                mix-blend-mode: multiply; /* Helps remove white background */
            }
            [data-theme='dark'] #tutorial-robot img {
                mix-blend-mode: screen; /* Adjust for dark mode if needed */
            }
            @keyframes robotWave {
                0%, 100% { transform: translateY(0) translateX(0) rotate(0); }
                25% { transform: translateY(-20px) translateX(10px) rotate(5deg); }
                50% { transform: translateY(5px) translateX(20px) rotate(-3deg); }
                75% { transform: translateY(-15px) translateX(10px) rotate(2deg); }
            }
            #tutorial-bubble {
                position: absolute;
                background: white;
                color: #0f172a;
                padding: 20px;
                border-radius: 20px;
                box-shadow: 0 15px 40px rgba(0,0,0,0.15);
                width: 250px;
                font-size: 14px;
                line-height: 1.5;
                font-family: 'Outfit', sans-serif;
                pointer-events: auto;
                opacity: 0;
                transform: scale(0.8) translateY(10px);
                transition: all 0.4s ease;
                border: 2px solid #f50e06;
            }
            [data-theme='dark'] #tutorial-bubble {
                background: #1e293b;
                color: #f1f5f9;
                box-shadow: 0 15px 40px rgba(0,0,0,0.4);
            }
            #tutorial-bubble.active {
                opacity: 1;
                transform: scale(1) translateY(0);
            }
            #tutorial-bubble::after {
                content: '';
                position: absolute;
                border: 10px solid transparent;
            }
            
            /* Positions */
            .pos-bottom { top: 110%; left: 50%; transform: translateX(-50%); }
            .pos-bottom::after { border-bottom-color: #f50e06; bottom: 100%; left: 50%; margin-left: -10px; }
            
            .pos-top { bottom: 110%; left: 50%; transform: translateX(-50%); }
            .pos-top::after { border-top-color: #f50e06; top: 100%; left: 50%; margin-left: -10px; }

            .pos-right { left: 110%; top: 50%; transform: translateY(-50%); }
            .pos-right::after { border-right-color: #f50e06; right: 100%; top: 50%; margin-top: -10px; }

            .pos-bottom-right { top: 90%; left: 80%; }
            .pos-bottom-right::after { border-bottom-color: #f50e06; bottom: 100%; left: 20px; }

            .pos-bottom-left { top: 90%; right: 80%; }
            .pos-bottom-left::after { border-bottom-color: #f50e06; bottom: 100%; right: 20px; }

            .tutorial-actions {
                display: flex;
                justify-content: space-between;
                margin-top: 15px;
                gap: 10px;
            }
            #tutorial-next {
                background: #f50e06;
                color: white;
                border: none;
                padding: 6px 15px;
                border-radius: 50px;
                font-weight: 700;
                cursor: pointer;
                font-size: 12px;
            }
            #tutorial-skip {
                background: #f1f5f9;
                color: #64748b;
                border: none;
                padding: 6px 15px;
                border-radius: 50px;
                font-weight: 700;
                cursor: pointer;
                font-size: 12px;
            }
            [data-theme='dark'] #tutorial-skip {
                background: #334155;
                color: #94a3b8;
            }
        `;
        document.head.appendChild(style);

        document.getElementById('tutorial-next').onclick = nextStep;
        document.getElementById('tutorial-skip').onclick = endTutorial;
    }

    function moveRobotToElement(elementId, position) {
        const el = document.getElementById(elementId);
        if (!el) {
            // If element missing (e.g. role specific), find next valid one
            nextStep();
            return;
        }

        const rect = el.getBoundingClientRect();
        const robotWidth = 120;
        const robotHeight = 120;

        let targetX, targetY;

        switch(position) {
            case 'bottom':
                targetX = rect.left + (rect.width / 2) - (robotWidth / 2);
                targetY = rect.bottom + 20;
                break;
            case 'bottom-right':
                targetX = rect.right - 20;
                targetY = rect.bottom + 10;
                break;
            case 'bottom-left':
                targetX = rect.left - robotWidth + 20;
                targetY = rect.bottom + 10;
                break;
            default:
                targetX = rect.left + (rect.width / 2) - (robotWidth / 2);
                targetY = rect.bottom + 20;
        }

        // Clamp to viewport
        targetX = Math.max(20, Math.min(window.innerWidth - robotWidth - 20, targetX));
        targetY = Math.max(20, Math.min(window.innerHeight - robotHeight - 20, targetY));

        robotEl.style.left = `${targetX}px`;
        robotEl.style.top = `${targetY}px`;
        robotEl.style.opacity = '1';

        // Update bubble text and position class
        const textEl = document.getElementById('tutorial-text');
        textEl.textContent = steps[currentStep].text;
        
        bubbleEl.className = 'active pos-' + position;
        
        const nextBtn = document.getElementById('tutorial-next');
        if (currentStep === steps.length - 1) {
            nextBtn.textContent = 'Finish';
        } else {
            nextBtn.textContent = 'Next';
        }
    }

    function nextStep() {
        bubbleEl.classList.remove('active');
        currentStep++;
        
        if (currentStep >= steps.length) {
            endTutorial();
            return;
        }

        setTimeout(() => {
            moveRobotToElement(steps[currentStep].id, steps[currentStep].position);
        }, 500);
    }

    function endTutorial() {
        if (!robotEl) return;
        robotEl.style.transition = 'all 1s ease-in';
        robotEl.style.transform = 'translateY(-200px) rotate(20deg)';
        robotEl.style.opacity = '0';
        setTimeout(() => {
            robotEl.remove();
            robotEl = null;
        }, 1000);
    }

    window.startTutorial = function() {
        createRobot();
        currentStep = 0;
        moveRobotToElement(steps[currentStep].id, steps[currentStep].position);
    };

})();
