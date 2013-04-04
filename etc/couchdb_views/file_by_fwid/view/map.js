function( doc ) {
	// usage example: http://host/hsn/_design/file_by_fwid/_view/view?key="100"
    if( doc.type == "file" ) {
        emit( doc.job, {'classification': doc.classification, 'top_ancestor': doc.top_ancestor, 'id': doc._id});
    }
}