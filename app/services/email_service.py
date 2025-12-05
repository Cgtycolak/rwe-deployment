"""
Email service for sending automated heatmap reports
"""
import os
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from datetime import datetime, timedelta
import pandas as pd
import plotly.graph_objects as go
from plotly.io import to_image
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending automated heatmap emails"""
    
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app config"""
        self.smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.environ.get('SMTP_PORT', '587'))
        self.sender_email = os.environ.get('SENDER_EMAIL')
        self.sender_password = os.environ.get('SENDER_PASSWORD')
        self.recipient_emails = os.environ.get('RECIPIENT_EMAILS', '').split(',')
        
        if not self.sender_email or not self.sender_password:
            logger.warning("Email credentials not configured. Email service will not work.")
    
    def create_heatmap_image(self, data, title, colorscale='RdBu', zmid=None):
        """
        Create a heatmap image from data
        
        Args:
            data: Dict with 'hours', 'plants', 'values'
            title: Title for the heatmap
            colorscale: Plotly colorscale (string name or list)
            zmid: Middle value for diverging colorscales
            
        Returns:
            bytes: PNG image data
        """
        try:
            values = data['values']
            hours = data['hours']
            plants = data['plants']
            
            # Find min and max for color scaling
            allValues = [val for row in values for val in row]
            maxValue = max(allValues)
            minValue = min(allValues)
            
            # Function to determine text color
            def getTextColor(value):
                if zmid is not None and value == 0:
                    return 'black'
                threshold = 0.3
                normalizedValue = (value - minValue) / (maxValue - minValue) if maxValue != minValue else 0.5
                return 'black' if normalizedValue > threshold else 'white'
            
            # Create annotations
            annotations = []
            for i, row in enumerate(values):
                for j, val in enumerate(row):
                    annotations.append({
                        'text': str(round(val)),
                        'x': j,
                        'y': i,
                        'xref': 'x',
                        'yref': 'y',
                        'showarrow': False,
                        'font': {
                            'size': 10,
                            'color': getTextColor(val)
                        }
                    })
            
            # Create layout
            layout = go.Layout(
                title={
                    'text': title,
                    'font': {'size': 16}
                },
                xaxis={
                    'title': '',
                    'tickangle': -90,
                    'ticktext': plants,
                    'tickvals': list(range(len(plants))),
                    'tickfont': {'size': 10},
                    'tickmode': 'array',
                    'side': 'bottom'
                },
                yaxis={
                    'title': 'Hour',
                    'ticktext': hours,
                    'tickvals': list(range(24)),
                    'autorange': 'reversed',
                    'tickfont': {'size': 10}
                },
                margin={'l': 80, 'r': 50, 'b': 250, 't': 80, 'pad': 4},
                width=1200,
                height=900,
                plot_bgcolor='white',
                paper_bgcolor='white',
                annotations=annotations
            )
            
            # Create heatmap trace
            heatmap_trace = go.Heatmap(
                z=values,
                x=plants,
                y=hours,
                colorscale=colorscale,
                reversescale=True,  # REVERSE the RdBu scale: Red (high) to Blue (low) to match dashboard
                showscale=True,
                colorbar={
                    'title': 'MWh',
                    'titleside': 'right',
                    'thickness': 25,
                    'len': 0.9
                },
                zmid=zmid,
                hoverongaps=False,
                xgap=1,
                ygap=1
            )
            
            # Create figure
            fig = go.Figure(data=[heatmap_trace], layout=layout)
            
            # Convert to image
            img_bytes = to_image(fig, format='png', width=1200, height=900, scale=2)
            
            return img_bytes
            
        except Exception as e:
            logger.error(f"Error creating heatmap image: {str(e)}")
            raise
    
    def send_daily_heatmap_report(self, date=None):
        """
        Send daily heatmap report email
        
        Args:
            date: Date to generate report for (defaults to yesterday)
        """
        if not self.sender_email or not self.sender_password:
            logger.error("Email credentials not configured")
            return False
        
        if not self.recipient_emails or not self.recipient_emails[0]:
            logger.error("No recipient emails configured")
            return False
        
        try:
            # Use yesterday's date if not specified
            if date is None:
                date = (datetime.now() - timedelta(days=1)).date()
            elif isinstance(date, str):
                date = datetime.strptime(date, '%Y-%m-%d').date()
            
            date_str = date.strftime('%Y-%m-%d')
            
            logger.info(f"Generating heatmap report for {date_str}")
            
            # Import here to avoid circular imports
            from app import create_app
            
            app = create_app()
            
            with app.app_context():
                # Fetch all heatmap data
                heatmaps = []
                
                # Natural Gas - First Version ONLY
                try:
                    ng_first = fetch_natural_gas_heatmap_data(date, 'first')
                    if ng_first and ng_first.get('code') == 200:
                        img = self.create_heatmap_image(
                            ng_first['data'],
                            f'Natural Gas DPP First Version - {date_str}',
                            colorscale='RdBu'  # Same as dashboard: Red (high) to Blue (low)
                        )
                        heatmaps.append(('natural_gas_first', img, 'Natural Gas - First Version'))
                except Exception as e:
                    logger.error(f"Error generating Natural Gas first version: {str(e)}")
                
                # Import Coal - First Version
                try:
                    ic_first = fetch_import_coal_heatmap_data(date, 'first')
                    if ic_first and ic_first.get('code') == 200:
                        img = self.create_heatmap_image(
                            ic_first['data'],
                            f'Import Coal DPP First Version - {date_str}',
                            colorscale='RdBu'  # Same as dashboard
                        )
                        heatmaps.append(('import_coal_first', img, 'Import Coal - First Version'))
                except Exception as e:
                    logger.error(f"Error generating Import Coal first version: {str(e)}")
                
                # Hydro - First Version
                try:
                    hydro_first = fetch_hydro_heatmap_data(date, 'first')
                    if hydro_first and hydro_first.get('code') == 200:
                        img = self.create_heatmap_image(
                            hydro_first['data'],
                            f'Hydro DPP First Version - {date_str}',
                            colorscale='RdBu'  # Same as dashboard
                        )
                        heatmaps.append(('hydro_first', img, 'Hydro - First Version'))
                except Exception as e:
                    logger.error(f"Error generating Hydro first version: {str(e)}")
                
                # Lignite - First Version
                try:
                    lignite_first = fetch_lignite_heatmap_data(date, 'first')
                    if lignite_first and lignite_first.get('code') == 200:
                        img = self.create_heatmap_image(
                            lignite_first['data'],
                            f'Lignite DPP First Version - {date_str}',
                            colorscale='RdBu'  # Same as dashboard
                        )
                        heatmaps.append(('lignite_first', img, 'Lignite - First Version'))
                except Exception as e:
                    logger.error(f"Error generating Lignite first version: {str(e)}")
                
                if not heatmaps:
                    logger.error("No heatmaps generated successfully")
                    return False
                
                # Create email
                msg = MIMEMultipart('related')
                msg['Subject'] = f'Daily Power Generation Heatmap Report - {date_str}'
                msg['From'] = self.sender_email
                msg['To'] = ', '.join(self.recipient_emails)
                
                # Create HTML body
                html_body = f"""
                <html>
                    <head></head>
                    <body style="font-family: Arial, sans-serif;">
                        <h2>Daily Power Generation Heatmap Report</h2>
                        <p><strong>Report Date:</strong> {date_str}</p>
                        <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                        <hr>
                        <p>This automated report contains the DPP (Day-Ahead Production Plan) heatmaps for various generation types.</p>
                        
                        <h3>Heatmaps:</h3>
                """
                
                # Add each heatmap to HTML
                for idx, (cid, img_data, title) in enumerate(heatmaps):
                    html_body += f"""
                        <div style="margin-bottom: 30px;">
                            <h4>{title}</h4>
                            <img src="cid:{cid}" style="max-width: 100%; height: auto;">
                        </div>
                    """
                
                html_body += """
                        <hr>
                        <p style="color: #666; font-size: 12px;">
                            This is an automated email from RWE Dashboard. 
                            For questions, please contact your system administrator.
                        </p>
                    </body>
                </html>
                """
                
                # Attach HTML body
                msg_alternative = MIMEMultipart('alternative')
                msg.attach(msg_alternative)
                msg_alternative.attach(MIMEText(html_body, 'html'))
                
                # Attach images
                for cid, img_data, title in heatmaps:
                    img = MIMEImage(img_data)
                    img.add_header('Content-ID', f'<{cid}>')
                    img.add_header('Content-Disposition', 'inline', filename=f'{cid}.png')
                    msg.attach(img)
                
                # Send email
                logger.info(f"Sending email to {self.recipient_emails}")
                
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.starttls()
                    server.login(self.sender_email, self.sender_password)
                    server.send_message(msg)
                
                logger.info("Email sent successfully")
                return True
                
        except Exception as e:
            logger.error(f"Error sending daily heatmap report: {str(e)}")
            return False


# Helper functions to fetch heatmap data (these will be imported from main.py)
def fetch_natural_gas_heatmap_data(date, version):
    """Fetch natural gas heatmap data"""
    from app.models.heatmap import NaturalGasHeatmapData
    from app.mappings import plant_mapping
    from app.main import process_heatmap_data
    
    heatmap_data = NaturalGasHeatmapData.query.filter_by(
        date=date,
        version=version
    ).all()
    
    if not heatmap_data:
        return None
    
    df = process_heatmap_data(heatmap_data, plant_mapping)
    
    if df.empty:
        return None
    
    return {
        "code": 200,
        "data": {
            "hours": df.index.tolist(),
            "plants": [f"{name}--{capacity} Mw" for name, capacity in zip(
                plant_mapping['plant_names'],
                plant_mapping['capacities']
            )],
            "values": df.values.tolist()
        }
    }


def fetch_import_coal_heatmap_data(date, version):
    """Fetch import coal heatmap data"""
    from app.models.heatmap import ImportedCoalHeatmapData
    from app.mappings import import_coal_mapping
    from app.main import process_heatmap_data
    
    heatmap_data = ImportedCoalHeatmapData.query.filter_by(
        date=date,
        version=version
    ).all()
    
    if not heatmap_data:
        return None
    
    df = process_heatmap_data(heatmap_data, import_coal_mapping)
    
    if df.empty:
        return None
    
    return {
        "code": 200,
        "data": {
            "hours": df.index.tolist(),
            "plants": [f"{name}--{capacity} Mw" for name, capacity in zip(
                import_coal_mapping['plant_names'],
                import_coal_mapping['capacities']
            )],
            "values": df.values.tolist()
        }
    }


def fetch_hydro_heatmap_data(date, version):
    """Fetch hydro heatmap data"""
    from app.models.heatmap import HydroHeatmapData
    from app.mappings import hydro_mapping
    from app.main import process_heatmap_data
    
    heatmap_data = HydroHeatmapData.query.filter_by(
        date=date,
        version=version
    ).all()
    
    if not heatmap_data:
        return None
    
    df = process_heatmap_data(heatmap_data, hydro_mapping)
    
    if df.empty:
        return None
    
    return {
        "code": 200,
        "data": {
            "hours": df.index.tolist(),
            "plants": [f"{name}--{capacity} Mw" for name, capacity in zip(
                hydro_mapping['plant_names'],
                hydro_mapping['capacities']
            )],
            "values": df.values.tolist()
        }
    }


def fetch_lignite_heatmap_data(date, version):
    """Fetch lignite heatmap data"""
    from app.models.heatmap import LigniteHeatmapData
    from app.mappings import lignite_mapping
    from app.main import process_heatmap_data
    
    heatmap_data = LigniteHeatmapData.query.filter_by(
        date=date,
        version=version
    ).all()
    
    if not heatmap_data:
        return None
    
    df = process_heatmap_data(heatmap_data, lignite_mapping)
    
    if df.empty:
        return None
    
    return {
        "code": 200,
        "data": {
            "hours": df.index.tolist(),
            "plants": [f"{name}--{capacity} MW" for name, capacity in zip(
                lignite_mapping['plant_names'],
                lignite_mapping['capacities']
            )],
            "values": df.values.tolist()
        }
    }

