function( doc ) {
	// usage example: http://host/hsn/_design/url_by_fwid/_view/view?key="100"
    if( doc.type == "url" ) {
        emit( doc.job, {'url': doc.url_original, 'classification': doc.classification, 'top_ancestor': doc.top_ancestor, 'id': doc._id});
    }
}