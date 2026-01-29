import os
import sys

# Add current dir to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from app import create_graph
    
    print("Generating graph...")
    app = create_graph()
    
    # Generate PNG
    png_data = app.get_graph().draw_mermaid_png()
    
    output_path = "ralph_graph.png"
    with open(output_path, "wb") as f:
        f.write(png_data)
        
    print(f"✅ Graph image saved to {output_path}")

except Exception as e:
    print(f"❌ Error generating graph: {e}")
