function(doc) {
	// usage example: http://host/hsn/_design/url_classification_count/_view/view?key="benign"
    if( doc.type == "url" ) {
        emit(doc.classification, 1);
    } 
}