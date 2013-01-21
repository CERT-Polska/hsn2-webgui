function( doc ) {
	// usage example: http://host/hsn/_design/analysis/_view/by_node?keys=["100:2", "100:3"]
    if( doc.type == "analysis" && doc.classification ) {
    	emit( doc.node, {analyzer: doc.service, classification: doc.classification});
    } else if ( doc.type == "analysis" ) {
    	emit( doc.node, {analyzer: doc.service});
    }
}