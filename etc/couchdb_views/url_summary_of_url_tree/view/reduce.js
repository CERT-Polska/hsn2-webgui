function(keys, values, rereduce) {
	
	var statusValues = {
			'unknown': 1,
			'benign': 2,
			'suspicious': 3,
			'malicious': 4,
		}	

	result = {
			classification: 'unknown',
			subpagesCount: 0,
			url: ''
		}	
	
	if ( rereduce ) {
		
		for(var i=0; i < values.length; ++i) {
			
			if ( statusValues[values[i]['classification']] > statusValues[result.classification] ) {
				result.classification = values[i]['classification'];
			}
			if ( values[i]['url'] ) {
				result.url = values[i]['url'];
			}

			result.subpagesCount += values[i]['subpagesCount'];
		}
		
		return result 
	} else {

		topAncestor = keys[0][0][0];

		for(var i=0; i < keys.length; ++i) {
			if ( statusValues[values[i]['classification']] > statusValues[result.classification] ) {
				result.classification = values[i]['classification']; 
			}
			result.subpagesCount += 1;
			
			if ( topAncestor == values[i]['id'].replace(/^\d+:(\d+)$/, '$1') ) {
				result.url = values[i]['url']
			}
		}
	}

	return result;
}