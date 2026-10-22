"""Login, logout, the dashboard shell and the internal reports."""
import hmac
from flask import Blueprint, session, render_template, redirect, url_for, request, current_app, send_from_directory
from ..functions import login_required
import os

pages_bp = Blueprint('pages', __name__)


@pages_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Get credentials from config (guaranteed non-None by factory startup assertion)
        correct_username = current_app.config['DASHBOARD_USERNAME']
        correct_password = current_app.config['DASHBOARD_PASSWORD']
        
        # compare_digest takes the same time whether the first or last character differs
        if (hmac.compare_digest((username or '').encode(), correct_username.encode())
                and hmac.compare_digest((password or '').encode(), correct_password.encode())):
            session['authenticated'] = True
            session['username'] = username
            session.permanent = True
            current_app.logger.info("Login success: user=%r ip=%s", username,
                                    request.headers.get('X-Forwarded-For', request.remote_addr))
            return redirect(url_for('pages.index'))
        else:
            current_app.logger.warning("Login failure: user=%r ip=%s", username,
                                       request.headers.get('X-Forwarded-For', request.remote_addr))
            return render_template('login.html', error='Invalid username or password')
    
    # If already authenticated, redirect to dashboard
    if session.get('authenticated'):
        return redirect(url_for('pages.index'))
    
    return render_template('login.html')


@pages_bp.route('/logout')
def logout():
    username = session.get('username', 'unknown')
    session.clear()
    current_app.logger.info("Logout: user=%r ip=%s", username,
                            request.headers.get('X-Forwarded-For', request.remote_addr))
    return redirect(url_for('pages.login'))


# Internal reports (gas consumption, gross margin). Kept out of /static so they need a login.
REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'reports')


@pages_bp.route('/reports/<path:name>')
@login_required
def report(name):
    return send_from_directory(REPORTS_DIR, name)


@pages_bp.route('/', methods=['GET'])
@login_required
def index():
    urls = {
        'getOrgs': url_for('plan_vs_realtime.get_orgs'),
        'getUevcbids': url_for('plan_vs_realtime.get_orgs_uevcbids'),
        'getDPPTable': url_for('plan_vs_realtime.get_dpp_data'),
        'getPowerPlants': url_for('plan_vs_realtime.get_powerplants'),
        'getRealtimeData': url_for('plan_vs_realtime.get_realtime_data'),
        # CAO charts (rolling-averages.js)
        'rollingData': url_for('cao_charts.get_rolling_data'),
        'rollingLastUpdate': url_for('cao_charts.get_rolling_last_update'),
        'demandData': url_for('cao_charts.get_demand_data'),
        'monthlyDemandData': url_for('cao_charts.get_monthly_demand_data'),
        'solarWeeklyData': url_for('cao_charts.get_solar_weekly_data'),
    }
    return render_template('index.html', urls=urls)
