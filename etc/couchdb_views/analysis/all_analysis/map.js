function(doc) {
	// usage example: http://host/hsn/_design/analysis/_view/all_analysis
    if( doc.type == "analysis" ) {
          emit( doc._id,  null);
    }
}