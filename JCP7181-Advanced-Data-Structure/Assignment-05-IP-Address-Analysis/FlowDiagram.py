import graphviz
import os

def create_workflow_graph():
    """
    Generates a visual workflow diagram (PNG) for the IP Address Analyzer program.
    This version is optimized for a Left-to-Right (landscape) layout
    with uniform font sizes for a professional appearance.
    """
    
    # Set the working directory to the script's directory
    try:
        # This helps ensure the output PNG is saved in the same place
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
    except Exception:
        # Fallback for environments where __file__ isn't available
        pass 

    print("Initializing workflow diagram...")

    # Create a new Digraph (Directed Graph)
    dot = graphviz.Digraph(
        comment='Comprehensive Workflow of IP Address Analyzer (JCP7181)',
        engine='dot'
    )
    
    # --- Graph Attributes (Landscape Layout) ---
    dot.attr(
        label='Comprehensive Workflow of IP Address Analyzer (JCP7181)',
        fontsize='20',
        fontname='Helvetica, Arial, sans-serif',
        rankdir='LR', # <<< --- EDITED: Left-to-Right for a shorter, wider graph
        size='11.7,8.3!', # A4 size in inches (Landscape)
        ratio='auto',
        dpi='600' 
    )
    
    # --- Node/Edge Default Styles ---
    dot.attr(
        'node', 
        shape='box', 
        style='rounded,filled', 
        fontname='Helvetica, Arial, sans-serif', 
        fontsize='11',     # <<< --- EDITED: Enforced uniform font size
        fillcolor='#F8F9FA', 
        width='2.2',         # <<< --- EDITED: Adjusted for LR layout
        height='1.0',        # <<< --- EDITED: Adjusted for LR layout
        fixedsize='false'  
    )
    dot.attr(
        'edge', 
        fontname='Helvetica, Arial, sans-serif', 
        fontsize='11'        # <<< --- EDITED: Uniform edge font size (was 10)
    )

    # --- Phase 1: Input & Reconstruction ---
    with dot.subgraph(name='cluster_phase1') as c:
        c.attr(label='Phase 1: Input & Reconstruction', 
               style='rounded', 
               fillcolor='#EAF2F8', 
               color='#2874A6',
               fontcolor='#2874A6',
               fontsize='14')
        
        c.node('START', 'Start', shape='ellipse', fillcolor='#D5F5E3')
        c.node('READ_INPUT', 'Read input.txt\nValidate Header (N, S)', shape='note', fillcolor='#FEF9E7')
        c.node('VALIDATE_CHECK', 'Valid?', shape='diamond', fillcolor='#FADBD8')
        c.node('MASTER_LIST_1', 'allReconstructedIPs\n(S={8, 16, 24})', shape='cylinder', fillcolor='#FDEBD0')

        c.edge('START', 'READ_INPUT')
        c.edge('READ_INPUT', 'VALIDATE_CHECK')
        c.edge('VALIDATE_CHECK', 'MASTER_LIST_1', label=' Yes (N, S)')

        # --- Sub-loop for N entries ---
        with dot.subgraph(name='cluster_loop_N') as sub_n:
            sub_n.attr(label='For each of N Log Entries', 
                       style='rounded,dashed', 
                       color='grey')
            
            sub_n.node('READ_LOG', 'Read Corrupted String', shape='box')
            
            # --- Backtracking internal logic ---
            with dot.subgraph(name='cluster_backtrack') as sub_bt:
                sub_bt.attr(label='Backtracking Function', style='rounded', fillcolor='#FFFFFF')
                sub_bt.node('BT_START', 'Try 1, 2, or 3 Digits', shape='box')
                sub_bt.node('BT_VALIDATE', 'isValidOctet(str)\n(0-255, no leading 0s)', shape='diamond')
                sub_bt.node('BT_RECURSE', 'Recurse', shape='ellipse')
                sub_bt.node('BT_BACKTRACK', 'Backtrack (pop_back)', shape='ellipse')
                sub_bt.node('BT_ADD', 'Found 4 Octets\n& End of String', shape='diamond')
                
                sub_bt.edge('BT_START', 'BT_VALIDATE')
                sub_bt.edge('BT_VALIDATE', 'BT_RECURSE', label=' Valid')
                sub_bt.edge('BT_RECURSE', 'BT_BACKTRACK')
                sub_bt.edge('BT_VALIDATE', 'BT_START', label=' Invalid')
                sub_bt.edge('BT_RECURSE', 'BT_ADD')
            
            sub_n.node('MASTER_LIST_2', 'allReconstructedIPs\n(Master List, size V)', shape='cylinder', fillcolor='#FDEBD0')

            sub_n.edge('READ_LOG', 'BT_START')
            sub_n.edge('BT_ADD', 'MASTER_LIST_2', label=' Adds Valid IPs')

        c.edge('VALIDATE_CHECK', 'READ_LOG')

    # --- Phase 2: Analysis & Clustering ---
    with dot.subgraph(name='cluster_phase2') as c:
        c.attr(label='Phase 2: Analysis & Clustering', 
               style='rounded', 
               fillcolor='#E8F8F5', 
               color='#16A085',
               fontcolor='#16A085',
               fontsize='14')
        
        c.node('ITERATE_V', 'For each of V\nReconstructed IPs', shape='box')

        with dot.subgraph(name='cluster_handshake') as sub_h:
            sub_h.attr(label='Core Analysis Handshake', style='rounded', fillcolor='#FFFFFF')
            sub_h.node('TRIE', 
                       'SubnetTrie (findAndSetRep.)\n\n'
                       '- Counts Unique Subnets\n'
                       '- Finds/Assigns a "Leader Index"',
                       shape='box', 
                       fillcolor='#D6EAF8') 
            
            sub_h.node('DSU', 
                       'ClusterUnion (DSU) (uniteSets)\n\n'
                       '- Merges IP\'s set with Leader\'s set\n'
                       '- Updates largestClusterSize',
                       shape='box', 
                       fillcolor='#D5F5E3') 
            
            sub_h.edge('TRIE', 'DSU', label=' Merges (IP Index, Leader Index)')

        c.edge('ITERATE_V', 'TRIE', label=' Queries')

    # --- Phase 3: Reporting ---
    with dot.subgraph(name='cluster_phase3') as c:
        c.attr(label='Phase 3: Finalization & Reporting', 
               style='rounded', 
               fillcolor='#FDF2E9', 
               color='#D35400',
               fontcolor='#D35400',
               fontsize='14')
        
        c.node('GET_COUNTS', 
               'Get Final Counts\n\n'
               '- uniqueSubnetCount (from Trie)\n'
               '- largestClusterSize (from DSU)', 
               shape='box')
        
        c.node('CHECK_N', 'N <= 5?', shape='diamond')
        c.node('WRITE_OPTIONAL', 'Write Optional IP List', shape='box')
        c.node('WRITE_SUMMARY', 'Write to output.txt\n(Mandatory: Final Summary)', shape='note', fillcolor='#FEF9E7')
        c.node('END', 'End', shape='ellipse', fillcolor='#D5F5E3')

        c.edge('GET_COUNTS', 'CHECK_N')
        c.edge('CHECK_N', 'WRITE_OPTIONAL', label=' Yes')
        c.edge('CHECK_N', 'WRITE_SUMMARY', label=' No')
        c.edge('WRITE_OPTIONAL', 'WRITE_SUMMARY')
        c.edge('WRITE_SUMMARY', 'END')

    # --- Overall Flow Edges (Connecting Phases) ---
    dot.edge('MASTER_LIST_2', 'ITERATE_V', style='invis') # Use invis to help layout
    dot.edge('DSU', 'GET_COUNTS', style='invis')
    
    # Link clusters explicitly for better flow
    dot.edge('VALIDATE_CHECK', 'READ_LOG', lhead='cluster_loop_N', ltail='cluster_phase1')
    dot.edge('MASTER_LIST_2', 'ITERATE_V', lhead='cluster_phase2', ltail='cluster_loop_N')
    dot.edge('DSU', 'GET_COUNTS', lhead='cluster_phase3', ltail='cluster_handshake')


    # --- Render the graph ---
    try:
        # Save as PNG
        # Set view=False as it's safer for WSL/headless environments
        dot.render('program_workflow', view=False, format='png', cleanup=True,
                   engine='dot') 
        print(f"\nSuccessfully generated 'program_workflow.png'")
        print("You can view the image in the VS Code file explorer.")
    except Exception as e:
        print(f"\nError: Could not render graph. Is Graphviz installed?")
        print(f"Details: {e}")
        print("Saving .dot source file as 'program_workflow.dot' instead.")
        dot.save('program_workflow.dot')

if __name__ == "__main__":
    create_workflow_graph()