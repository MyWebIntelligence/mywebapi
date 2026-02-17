import React, {useContext, useEffect} from 'react';
import {Context} from '../../app/Context';
import FormControl from 'react-bootstrap/FormControl';
import InputGroup from 'react-bootstrap/InputGroup';

function DatabaseLocator() {
    const context = useContext(Context);

    useEffect(() => {
        setTimeout(() => {
            context.setDb(localStorage.getItem('dbFile'));
        }, 1000);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    let stateClass = 'text-danger fas fa-exclamation-circle';

    if (context.connecting) {
        stateClass = 'text-warning fas fa-spinner spin';
    } else if (context.isConnected) {
        stateClass = 'text-success fas fa-check-circle';
    }

    return (
        <InputGroup>
            <InputGroup.Text><i className="fas fa-database" /></InputGroup.Text>
            <FormControl id="dbLocation" onBlur={e => context.setDb(e.target.value)}
                         defaultValue={localStorage.getItem('dbFile')}
                         placeholder="Paste database file path here"/>
            <InputGroup.Text>
                <i className={stateClass}> </i>
            </InputGroup.Text>
        </InputGroup>
    )
}

export default DatabaseLocator;
