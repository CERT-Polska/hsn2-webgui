function(doc) {
	// usage example: http://host/hsn/_design/analysis/_view/by_id_classification?keys=["100:2:js-sta", "100:3:js-sta"]
    if( doc.type == "analysis" && doc.classification ) {
          emit( doc._id,  doc.classification );
    }
}